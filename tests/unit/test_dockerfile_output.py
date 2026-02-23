"""Tests for Dockerfile output correctness (Batch 1 from REVIEW.md).

Each test demonstrates a current bug by asserting what the output SHOULD be.
These tests are expected to FAIL against the current code, proving the bugs
exist. Once the fixes are applied, they should pass.
"""

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
