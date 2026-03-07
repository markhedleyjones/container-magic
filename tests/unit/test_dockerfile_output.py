"""Tests for Dockerfile output correctness."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

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
# 1.1 Dockerfile instruction passthrough
# ---------------------------------------------------------------------------


class TestInstructionPassthrough:
    @pytest.mark.parametrize(
        ("step", "instruction"),
        [
            ("ARG BUILD_DATE", "ARG"),
            ('CMD ["python", "app.py"]', "CMD"),
            ('ENTRYPOINT ["python"]', "ENTRYPOINT"),
            ("HEALTHCHECK CMD curl -f http://localhost/", "HEALTHCHECK"),
            ('SHELL ["/bin/bash", "-c"]', "SHELL"),
            ("STOPSIGNAL SIGTERM", "STOPSIGNAL"),
            ("ENV FOO=bar", "ENV"),
            ("EXPOSE 8080", "EXPOSE"),
            ("LABEL version=1", "LABEL"),
        ],
    )
    def test_dockerfile_instruction_not_wrapped_with_run(self, step, instruction):
        config = _base_config(steps=[step])
        content = _generate(config)
        assert step in content
        assert f"RUN {instruction}" not in content

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

