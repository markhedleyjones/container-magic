"""Unit tests for container build logic."""

import os
from unittest.mock import MagicMock, patch

import pytest

from container_magic.core.builder import build_container
from container_magic.core.config import ContainerMagicConfig


def _make_config(**overrides):
    """Create a minimal config for testing."""
    data = {
        "names": {"image": "test-project", "user": "nonroot", "workspace": "workspace"},
        "stages": {
            "base": {
                "from": "ubuntu:22.04",
                "steps": [{"create": "user"}, {"become": "user"}],
            },
            "development": {"from": "base"},
            "production": {
                "from": "base",
                "steps": [{"copy": "workspace"}],
            },
        },
    }
    data.update(overrides)
    return ContainerMagicConfig(**data)


@pytest.fixture
def build_env(tmp_path):
    """Set up mocked build environment, returning a helper to run builds and inspect commands."""
    from contextlib import ExitStack

    from container_magic.core.runtime import Runtime

    with ExitStack() as stack:
        mock_get_runtime = stack.enter_context(
            patch("container_magic.core.builder.get_runtime")
        )
        mock_run = stack.enter_context(
            patch("container_magic.core.builder.subprocess.run")
        )
        mock_gen_dockerfile = stack.enter_context(
            patch("container_magic.generators.dockerfile.generate_dockerfile")
        )
        mock_gen_build = stack.enter_context(
            patch("container_magic.generators.build_script.generate_build_script")
        )
        mock_gen_run = stack.enter_context(
            patch("container_magic.generators.run_script.generate_run_script")
        )
        stack.enter_context(
            patch(
                "container_magic.core.builder.scan_workspace_symlinks", return_value=[]
            )
        )

        mock_get_runtime.return_value = Runtime.DOCKER
        mock_run.return_value = MagicMock(returncode=0)
        (tmp_path / "workspace").mkdir()

        class BuildEnv:
            path = tmp_path
            run = mock_run
            gen_dockerfile = mock_gen_dockerfile
            gen_build = mock_gen_build
            gen_run = mock_gen_run

            @staticmethod
            def build_cmd():
                return mock_run.call_args.args[0]

            @staticmethod
            def build_cmd_str():
                return " ".join(mock_run.call_args.args[0])

        yield BuildEnv()


class TestBuildContainer:
    def test_development_build_args(self, build_env):
        config = _make_config()
        build_container(config, build_env.path, target="development")

        build_cmd = build_env.build_cmd()
        assert "docker" == build_cmd[0]
        assert "build" == build_cmd[1]
        assert "--target" in build_cmd
        assert build_cmd[build_cmd.index("--target") + 1] == "development"
        assert f"USER_NAME={os.environ.get('USER', 'nonroot')}" in " ".join(build_cmd)
        assert f"USER_UID={os.getuid()}" in " ".join(build_cmd)
        assert f"USER_GID={os.getgid()}" in " ".join(build_cmd)
        assert "--tag" in build_cmd
        assert build_cmd[build_cmd.index("--tag") + 1] == "test-project:development"

    def test_production_build_args(self, build_env):
        config = _make_config()
        build_container(config, build_env.path, target="production")

        build_cmd = build_env.build_cmd()
        assert build_cmd[build_cmd.index("--target") + 1] == "production"
        assert build_cmd[build_cmd.index("--tag") + 1] == "test-project:production"
        assert "USER_NAME=nonroot" in " ".join(build_cmd)
        assert "USER_UID=1000" in " ".join(build_cmd)
        assert "USER_GID=1000" in " ".join(build_cmd)
        assert "USER_HOME=" not in " ".join(build_cmd)

    def test_arbitrary_target(self, build_env):
        config = _make_config()
        build_container(config, build_env.path, target="testing")

        build_cmd = build_env.build_cmd()
        assert build_cmd[build_cmd.index("--target") + 1] == "testing"
        assert build_cmd[build_cmd.index("--tag") + 1] == "test-project:testing"
        assert "USER_NAME=nonroot" in " ".join(build_cmd)
        assert "USER_UID=1000" in " ".join(build_cmd)
        assert "USER_GID=1000" in " ".join(build_cmd)
        assert "USER_HOME=" not in " ".join(build_cmd)

    def test_custom_tag(self, build_env):
        config = _make_config()
        build_container(config, build_env.path, target="production", tag="v1.0")

        build_cmd = build_env.build_cmd()
        assert build_cmd[build_cmd.index("--tag") + 1] == "test-project:v1.0"

    def test_development_includes_user_home(self, build_env):
        config = _make_config()
        build_container(config, build_env.path, target="development")
        assert "USER_HOME=" in build_env.build_cmd_str()

    def test_production_no_user_home(self, build_env):
        config = _make_config()
        build_container(config, build_env.path, target="production")
        assert "USER_HOME=" not in build_env.build_cmd_str()

    def test_root_user_build(self, build_env):
        config = _make_config(
            stages={
                "base": {"from": "ubuntu:22.04"},
                "development": {"from": "base"},
                "production": {"from": "base"},
            }
        )
        build_container(config, build_env.path, target="production")

        cmd = build_env.build_cmd_str()
        assert "USER_NAME=root" in cmd
        assert "USER_UID=0" in cmd
        assert "USER_GID=0" in cmd

    def test_regenerates_files_before_build(self, build_env):
        config = _make_config()
        build_container(config, build_env.path)

        build_env.gen_dockerfile.assert_called_once()
        build_env.gen_build.assert_called_once()
        build_env.gen_run.assert_called_once()

    def test_returns_exit_code(self, build_env):
        build_env.run.return_value = MagicMock(returncode=42)
        config = _make_config()
        result = build_container(config, build_env.path)
        assert result == 42
