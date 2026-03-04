"""Tests for Dockerfile output correctness."""

from pathlib import Path
from tempfile import TemporaryDirectory

from container_magic.core.config import ContainerMagicConfig
from container_magic.generators.dockerfile import generate_dockerfile


def _generate(config_dict):
    """Generate a Dockerfile from a config dict and return its content."""
    config = ContainerMagicConfig(**config_dict)
    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        generate_dockerfile(config, output_path)
        return output_path.read_text()


def _base_config(**overrides):
    """Minimal valid config with overrides applied to the base stage."""
    config = {
        "project": {"name": "test", "workspace": "workspace"},
        "stages": {
            "base": {"from": "python:3-slim", **overrides},
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    return config


# ---------------------------------------------------------------------------
# 1.1 ENV values with spaces
# ---------------------------------------------------------------------------


class TestEnvValueQuoting:
    def test_env_value_with_spaces(self):
        """ENV values containing spaces must be quoted in the Dockerfile."""
        config = _base_config(
            env={"MY_VAR": "hello world"},
            steps=[],
        )
        content = _generate(config)
        # Docker parses unquoted `ENV MY_VAR=hello world` as two assignments:
        # MY_VAR=hello and world= (empty). The value must be quoted.
        assert 'ENV MY_VAR="hello world"' in content

    def test_env_value_with_equals_sign(self):
        """ENV values containing = should be quoted for consistency.

        Docker splits on the first = only, so = in values technically works
        unquoted. But quoting all values uniformly is safer and more readable.
        """
        config = _base_config(
            env={"DATABASE_URL": "postgres://host:5432/db?opt=val"},
            steps=[],
        )
        content = _generate(config)
        assert 'ENV DATABASE_URL="postgres://host:5432/db?opt=val"' in content

    def test_env_value_simple_no_spaces(self):
        """Simple values without spaces should still work (quoting is harmless)."""
        config = _base_config(
            env={"MY_VAR": "hello"},
            steps=[],
        )
        content = _generate(config)
        # Either quoted or unquoted is fine for simple values
        assert "ENV MY_VAR=" in content
        assert "hello" in content

    def test_env_value_with_dollar_sign(self):
        """ENV values referencing other variables should be preserved."""
        config = _base_config(
            env={"PATH": "/app/bin:${PATH}"},
            steps=[],
        )
        content = _generate(config)
        # The ${PATH} reference must survive into the Dockerfile
        assert "${PATH}" in content


# ---------------------------------------------------------------------------
# 1.2 Missing Dockerfile instruction passthrough
# ---------------------------------------------------------------------------


class TestInstructionPassthrough:
    def test_arg_instruction_not_wrapped_with_run(self):
        """A custom step starting with ARG should not get a RUN prefix."""
        config = _base_config(steps=["ARG BUILD_DATE"])
        content = _generate(config)
        assert "ARG BUILD_DATE" in content
        assert "RUN ARG BUILD_DATE" not in content

    def test_cmd_instruction_not_wrapped_with_run(self):
        """A custom step starting with CMD should not get a RUN prefix."""
        config = _base_config(steps=['CMD ["python", "app.py"]'])
        content = _generate(config)
        assert 'CMD ["python", "app.py"]' in content
        assert "RUN CMD" not in content

    def test_entrypoint_instruction_not_wrapped_with_run(self):
        """A custom step starting with ENTRYPOINT should not get a RUN prefix."""
        config = _base_config(steps=['ENTRYPOINT ["python"]'])
        content = _generate(config)
        assert 'ENTRYPOINT ["python"]' in content
        assert "RUN ENTRYPOINT" not in content

    def test_healthcheck_instruction_not_wrapped_with_run(self):
        """A custom step starting with HEALTHCHECK should not get a RUN prefix."""
        config = _base_config(steps=["HEALTHCHECK CMD curl -f http://localhost/"])
        content = _generate(config)
        assert "HEALTHCHECK CMD curl -f http://localhost/" in content
        assert "RUN HEALTHCHECK" not in content

    def test_shell_instruction_not_wrapped_with_run(self):
        """A custom step starting with SHELL should not get a RUN prefix."""
        config = _base_config(steps=['SHELL ["/bin/bash", "-c"]'])
        content = _generate(config)
        assert 'SHELL ["/bin/bash", "-c"]' in content
        assert "RUN SHELL" not in content

    def test_stopsignal_instruction_not_wrapped_with_run(self):
        """A custom step starting with STOPSIGNAL should not get a RUN prefix."""
        config = _base_config(steps=["STOPSIGNAL SIGTERM"])
        content = _generate(config)
        assert "STOPSIGNAL SIGTERM" in content
        assert "RUN STOPSIGNAL" not in content

    def test_existing_passthrough_still_works(self):
        """Existing passthrough instructions (ENV, COPY, etc.) still work."""
        config = _base_config(steps=["ENV FOO=bar", "EXPOSE 8080", "LABEL version=1"])
        content = _generate(config)
        assert "ENV FOO=bar" in content
        assert "RUN ENV" not in content
        assert "EXPOSE 8080" in content
        assert "RUN EXPOSE" not in content
        assert "LABEL version=1" in content
        assert "RUN LABEL" not in content

    def test_plain_command_still_gets_run(self):
        """A non-instruction command should still get a RUN prefix."""
        config = _base_config(steps=["echo hello"])
        content = _generate(config)
        assert "RUN echo hello" in content


# ---------------------------------------------------------------------------
# 1.3 Multi-line step starting with non-RUN instruction
# ---------------------------------------------------------------------------


class TestMultiLineSteps:
    def test_multiline_run_command_joined_correctly(self):
        """Multi-line RUN commands should be joined with && (existing behaviour)."""
        config = _base_config(
            steps=["apt-get update\napt-get install -y curl"],
        )
        content = _generate(config)
        assert "RUN apt-get update" in content
        assert "apt-get install -y curl" in content

    def test_multiline_with_explicit_run_prefix(self):
        """Multi-line step starting with RUN should be joined correctly."""
        config = _base_config(
            steps=["RUN apt-get update\napt-get install -y curl"],
        )
        content = _generate(config)
        # The RUN prefix from the passthrough check should appear once,
        # and the lines should be joined with &&
        assert "apt-get update" in content
        assert "apt-get install -y curl" in content


# ---------------------------------------------------------------------------
# 1.4 Empty copy step arguments
# ---------------------------------------------------------------------------


class TestEmptyCopyArgs:
    def _assert_no_bare_copy(self, content):
        """Assert no COPY line has insufficient arguments."""
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("COPY"):
                parts = stripped.split()
                non_flag_parts = [p for p in parts if not p.startswith("--")]
                assert len(non_flag_parts) >= 3, (
                    f"COPY with insufficient arguments: {stripped}"
                )

    def test_copy_with_no_arguments(self):
        """A copy step with no arguments should raise or not produce a bare COPY."""
        config = _base_config(steps=["copy "])
        try:
            content = _generate(config)
            self._assert_no_bare_copy(content)
        except (ValueError, KeyError):
            pass  # Raising an error is also acceptable

    def test_copy_as_user_with_no_arguments(self):
        """A copy_as_user step with no arguments should raise or not produce a bare COPY."""
        config = _base_config(steps=["copy_as_user "])
        config["user"] = {"production": {"name": "testuser"}}
        config["stages"]["base"]["steps"] = [
            "create_user",
            "become_user",
            "copy_as_user ",
        ]
        try:
            content = _generate(config)
            self._assert_no_bare_copy(content)
        except (ValueError, KeyError):
            pass  # Raising an error is also acceptable


# ---------------------------------------------------------------------------
# 2.1 Stage preamble variants
# ---------------------------------------------------------------------------


def _get_stage_block(content, stage_name):
    """Extract lines for a single stage from a generated Dockerfile."""
    lines = content.splitlines()
    start = None
    end = None
    for i, line in enumerate(lines):
        if "FROM " in line and f" AS {stage_name}" in line:
            start = i
        elif start is not None and line.startswith("FROM "):
            end = i
            break
    if start is not None:
        return "\n".join(lines[start : end if end else len(lines)])
    return ""


class TestStagePreamble:
    def test_image_stage_with_user_args(self):
        """FROM Docker image with user steps: full ARG block + WORKSPACE + WORKDIR."""
        config = {
            "project": {"name": "test", "workspace": "ws"},
            "user": {"production": {"name": "app"}},
            "stages": {
                "base": {
                    "from": "python:3-slim",
                    "steps": ["create_user", "become_user"],
                },
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
            },
        }
        content = _generate(config)
        base = _get_stage_block(content, "base")
        assert "ARG USER_GID=" in base
        assert "USER_UID=" in base
        assert "USER_NAME=app" in base
        assert "USER_HOME=/home/app" in base
        assert "WORKSPACE_NAME=ws" in base
        assert "ENV WORKSPACE=${USER_HOME}/${WORKSPACE_NAME}" in base
        assert "WORKDIR ${USER_HOME}" in base

    def test_image_stage_without_user_args(self):
        """FROM Docker image without user steps: minimal ARG + WORKSPACE + WORKDIR."""
        config = _base_config(steps=[])
        content = _generate(config)
        base = _get_stage_block(content, "base")
        assert "ARG USER_HOME=" in base
        assert "WORKSPACE_NAME=" in base
        assert "ENV WORKSPACE=${USER_HOME}/${WORKSPACE_NAME}" in base
        assert "WORKDIR ${USER_HOME}" in base
        # No user-specific ARGs
        assert "USER_GID" not in base
        assert "USER_UID" not in base
        assert "USER_NAME" not in base

    def test_child_stage_with_user_args(self):
        """FROM another stage with user steps: user ARGs only, no WORKSPACE/WORKDIR."""
        config = {
            "project": {"name": "test", "workspace": "ws"},
            "user": {"production": {"name": "app"}},
            "stages": {
                "base": {"from": "python:3-slim", "steps": ["create_user"]},
                "development": {"from": "base", "steps": []},
                "production": {
                    "from": "base",
                    "steps": ["become_user", "copy_workspace"],
                },
            },
        }
        content = _generate(config)
        prod = _get_stage_block(content, "production")
        assert "ARG USER_GID=" in prod
        assert "USER_NAME=app" in prod
        # No workspace setup (inherited from parent)
        assert "WORKSPACE_NAME" not in prod
        assert "WORKDIR" not in prod

    def test_child_stage_without_user_args(self):
        """FROM another stage without user steps: completely empty preamble."""
        config = _base_config(steps=[])
        content = _generate(config)
        dev = _get_stage_block(content, "development")
        # No ARG, ENV, or WORKDIR lines
        assert "ARG " not in dev
        assert "ENV " not in dev
        assert "WORKDIR" not in dev

    def test_no_env_workdir_in_output(self):
        """ENV WORKDIR should never appear (removed variable)."""
        config = _base_config(steps=[])
        content = _generate(config)
        assert "ENV WORKDIR" not in content


# ---------------------------------------------------------------------------
# 2.2 ENV merging
# ---------------------------------------------------------------------------


class TestEnvMerging:
    def test_consecutive_env_steps_merged(self):
        """Consecutive env steps produce a single ENV instruction."""
        config = _base_config(
            steps=[
                {"env": {"PATH": "/usr/local/bin:$PATH"}},
                {"env": {"LD_LIBRARY_PATH": "/usr/local/lib"}},
            ],
        )
        content = _generate(config)
        base = _get_stage_block(content, "base")
        # Should be a single ENV with backslash continuation
        assert 'ENV PATH="/usr/local/bin:$PATH" \\' in base
        assert '    LD_LIBRARY_PATH="/usr/local/lib"' in base

    def test_non_consecutive_env_steps_not_merged(self):
        """Env steps separated by other steps remain separate."""
        config = _base_config(
            steps=[
                {"env": {"FOO": "bar"}},
                "echo hello",
                {"env": {"BAZ": "qux"}},
            ],
        )
        content = _generate(config)
        base = _get_stage_block(content, "base")
        assert 'ENV FOO="bar"' in base
        assert 'ENV BAZ="qux"' in base

    def test_single_env_step_no_continuation(self):
        """Single-var env step produces a simple ENV line."""
        config = _base_config(
            steps=[{"env": {"MY_VAR": "value"}}],
        )
        content = _generate(config)
        assert 'ENV MY_VAR="value"' in content
        # No backslash
        for line in content.splitlines():
            if "MY_VAR" in line:
                assert "\\" not in line

    def test_stage_level_env_vars_merged(self):
        """Multiple stage-level env vars produce a single merged ENV block."""
        config = _base_config(
            env={"A": "1", "B": "2"},
            steps=[],
        )
        content = _generate(config)
        base = _get_stage_block(content, "base")
        # Two vars on one ENV instruction
        env_lines = [
            line for line in base.splitlines() if line.strip().startswith("ENV")
        ]
        # The preamble ENV and the env_vars ENV
        env_var_lines = [line for line in env_lines if "A=" in line or "B=" in line]
        assert len(env_var_lines) == 1
        assert "\\" in env_var_lines[0]

    def test_single_stage_level_env_no_continuation(self):
        """Single stage-level env var produces a simple ENV line."""
        config = _base_config(
            env={"ONLY": "one"},
            steps=[],
        )
        content = _generate(config)
        assert 'ENV ONLY="one"' in content
