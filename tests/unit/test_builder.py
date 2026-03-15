"""Unit tests for container build logic."""

import os
from unittest.mock import MagicMock, patch


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


class TestBuildContainer:
    @patch("container_magic.core.builder.scan_workspace_symlinks", return_value=[])
    @patch("container_magic.generators.run_script.generate_run_script")
    @patch("container_magic.generators.build_script.generate_build_script")
    @patch("container_magic.generators.dockerfile.generate_dockerfile")
    @patch("container_magic.core.builder.subprocess.run")
    @patch("container_magic.core.builder.get_runtime")
    def test_development_build_args(
        self,
        mock_get_runtime,
        mock_run,
        mock_gen_dockerfile,
        mock_gen_build,
        mock_gen_run,
        mock_symlinks,
        tmp_path,
    ):
        from container_magic.core.runtime import Runtime

        mock_get_runtime.return_value = Runtime.DOCKER
        mock_run.return_value = MagicMock(returncode=0)

        (tmp_path / "workspace").mkdir()
        config = _make_config()

        build_container(config, tmp_path, target="development")

        build_cmd = mock_run.call_args.args[0]
        assert "docker" == build_cmd[0]
        assert "build" == build_cmd[1]
        assert "--target" in build_cmd
        assert build_cmd[build_cmd.index("--target") + 1] == "development"
        assert f"USER_NAME={os.environ.get('USER', 'nonroot')}" in " ".join(build_cmd)
        assert f"USER_UID={os.getuid()}" in " ".join(build_cmd)
        assert f"USER_GID={os.getgid()}" in " ".join(build_cmd)
        assert "--tag" in build_cmd
        assert build_cmd[build_cmd.index("--tag") + 1] == "test-project:development"

    @patch("container_magic.core.builder.scan_workspace_symlinks", return_value=[])
    @patch("container_magic.generators.run_script.generate_run_script")
    @patch("container_magic.generators.build_script.generate_build_script")
    @patch("container_magic.generators.dockerfile.generate_dockerfile")
    @patch("container_magic.core.builder.subprocess.run")
    @patch("container_magic.core.builder.get_runtime")
    def test_production_build_args(
        self,
        mock_get_runtime,
        mock_run,
        mock_gen_dockerfile,
        mock_gen_build,
        mock_gen_run,
        mock_symlinks,
        tmp_path,
    ):
        from container_magic.core.runtime import Runtime

        mock_get_runtime.return_value = Runtime.DOCKER
        mock_run.return_value = MagicMock(returncode=0)

        (tmp_path / "workspace").mkdir()
        config = _make_config()

        build_container(config, tmp_path, target="production")

        build_cmd = mock_run.call_args.args[0]
        assert build_cmd[build_cmd.index("--target") + 1] == "production"
        assert build_cmd[build_cmd.index("--tag") + 1] == "test-project:production"
        assert "USER_NAME=nonroot" in " ".join(build_cmd)
        assert "USER_UID=1000" in " ".join(build_cmd)
        assert "USER_GID=1000" in " ".join(build_cmd)

    @patch("container_magic.core.builder.scan_workspace_symlinks", return_value=[])
    @patch("container_magic.generators.run_script.generate_run_script")
    @patch("container_magic.generators.build_script.generate_build_script")
    @patch("container_magic.generators.dockerfile.generate_dockerfile")
    @patch("container_magic.core.builder.subprocess.run")
    @patch("container_magic.core.builder.get_runtime")
    def test_arbitrary_target(
        self,
        mock_get_runtime,
        mock_run,
        mock_gen_dockerfile,
        mock_gen_build,
        mock_gen_run,
        mock_symlinks,
        tmp_path,
    ):
        from container_magic.core.runtime import Runtime

        mock_get_runtime.return_value = Runtime.DOCKER
        mock_run.return_value = MagicMock(returncode=0)

        (tmp_path / "workspace").mkdir()
        config = _make_config()

        build_container(config, tmp_path, target="testing")

        build_cmd = mock_run.call_args.args[0]
        assert build_cmd[build_cmd.index("--target") + 1] == "testing"
        assert build_cmd[build_cmd.index("--tag") + 1] == "test-project:testing"
        assert "USER_NAME=nonroot" in " ".join(build_cmd)
        assert "USER_UID=1000" in " ".join(build_cmd)
        assert "USER_GID=1000" in " ".join(build_cmd)
        assert "USER_HOME=" not in " ".join(build_cmd)

    @patch("container_magic.core.builder.scan_workspace_symlinks", return_value=[])
    @patch("container_magic.generators.run_script.generate_run_script")
    @patch("container_magic.generators.build_script.generate_build_script")
    @patch("container_magic.generators.dockerfile.generate_dockerfile")
    @patch("container_magic.core.builder.subprocess.run")
    @patch("container_magic.core.builder.get_runtime")
    def test_custom_tag(
        self,
        mock_get_runtime,
        mock_run,
        mock_gen_dockerfile,
        mock_gen_build,
        mock_gen_run,
        mock_symlinks,
        tmp_path,
    ):
        from container_magic.core.runtime import Runtime

        mock_get_runtime.return_value = Runtime.DOCKER
        mock_run.return_value = MagicMock(returncode=0)

        (tmp_path / "workspace").mkdir()
        config = _make_config()

        build_container(config, tmp_path, target="production", tag="v1.0")

        build_cmd = mock_run.call_args.args[0]
        assert build_cmd[build_cmd.index("--tag") + 1] == "test-project:v1.0"

    @patch("container_magic.core.builder.scan_workspace_symlinks", return_value=[])
    @patch("container_magic.generators.run_script.generate_run_script")
    @patch("container_magic.generators.build_script.generate_build_script")
    @patch("container_magic.generators.dockerfile.generate_dockerfile")
    @patch("container_magic.core.builder.subprocess.run")
    @patch("container_magic.core.builder.get_runtime")
    def test_development_includes_user_home(
        self,
        mock_get_runtime,
        mock_run,
        mock_gen_dockerfile,
        mock_gen_build,
        mock_gen_run,
        mock_symlinks,
        tmp_path,
    ):
        from container_magic.core.runtime import Runtime

        mock_get_runtime.return_value = Runtime.DOCKER
        mock_run.return_value = MagicMock(returncode=0)

        (tmp_path / "workspace").mkdir()
        config = _make_config()

        build_container(config, tmp_path, target="development")

        build_cmd = " ".join(mock_run.call_args.args[0])
        assert "USER_HOME=" in build_cmd

    @patch("container_magic.core.builder.scan_workspace_symlinks", return_value=[])
    @patch("container_magic.generators.run_script.generate_run_script")
    @patch("container_magic.generators.build_script.generate_build_script")
    @patch("container_magic.generators.dockerfile.generate_dockerfile")
    @patch("container_magic.core.builder.subprocess.run")
    @patch("container_magic.core.builder.get_runtime")
    def test_production_no_user_home(
        self,
        mock_get_runtime,
        mock_run,
        mock_gen_dockerfile,
        mock_gen_build,
        mock_gen_run,
        mock_symlinks,
        tmp_path,
    ):
        from container_magic.core.runtime import Runtime

        mock_get_runtime.return_value = Runtime.DOCKER
        mock_run.return_value = MagicMock(returncode=0)

        (tmp_path / "workspace").mkdir()
        config = _make_config()

        build_container(config, tmp_path, target="production")

        build_cmd = " ".join(mock_run.call_args.args[0])
        assert "USER_HOME=" not in build_cmd

    @patch("container_magic.core.builder.scan_workspace_symlinks", return_value=[])
    @patch("container_magic.generators.run_script.generate_run_script")
    @patch("container_magic.generators.build_script.generate_build_script")
    @patch("container_magic.generators.dockerfile.generate_dockerfile")
    @patch("container_magic.core.builder.subprocess.run")
    @patch("container_magic.core.builder.get_runtime")
    def test_root_user_build(
        self,
        mock_get_runtime,
        mock_run,
        mock_gen_dockerfile,
        mock_gen_build,
        mock_gen_run,
        mock_symlinks,
        tmp_path,
    ):
        from container_magic.core.runtime import Runtime

        mock_get_runtime.return_value = Runtime.DOCKER
        mock_run.return_value = MagicMock(returncode=0)

        (tmp_path / "workspace").mkdir()
        config = _make_config(
            stages={
                "base": {"from": "ubuntu:22.04"},
                "development": {"from": "base"},
                "production": {"from": "base"},
            }
        )

        build_container(config, tmp_path, target="production")

        build_cmd = " ".join(mock_run.call_args.args[0])
        assert "USER_NAME=root" in build_cmd
        assert "USER_UID=0" in build_cmd
        assert "USER_GID=0" in build_cmd

    @patch("container_magic.core.builder.scan_workspace_symlinks", return_value=[])
    @patch("container_magic.generators.run_script.generate_run_script")
    @patch("container_magic.generators.build_script.generate_build_script")
    @patch("container_magic.generators.dockerfile.generate_dockerfile")
    @patch("container_magic.core.builder.subprocess.run")
    @patch("container_magic.core.builder.get_runtime")
    def test_regenerates_files_before_build(
        self,
        mock_get_runtime,
        mock_run,
        mock_gen_dockerfile,
        mock_gen_build,
        mock_gen_run,
        mock_symlinks,
        tmp_path,
    ):
        from container_magic.core.runtime import Runtime

        mock_get_runtime.return_value = Runtime.DOCKER
        mock_run.return_value = MagicMock(returncode=0)

        (tmp_path / "workspace").mkdir()
        config = _make_config()

        build_container(config, tmp_path)

        mock_gen_dockerfile.assert_called_once()
        mock_gen_build.assert_called_once()
        mock_gen_run.assert_called_once()

    @patch("container_magic.core.builder.scan_workspace_symlinks", return_value=[])
    @patch("container_magic.generators.run_script.generate_run_script")
    @patch("container_magic.generators.build_script.generate_build_script")
    @patch("container_magic.generators.dockerfile.generate_dockerfile")
    @patch("container_magic.core.builder.subprocess.run")
    @patch("container_magic.core.builder.get_runtime")
    def test_returns_exit_code(
        self,
        mock_get_runtime,
        mock_run,
        mock_gen_dockerfile,
        mock_gen_build,
        mock_gen_run,
        mock_symlinks,
        tmp_path,
    ):
        from container_magic.core.runtime import Runtime

        mock_get_runtime.return_value = Runtime.DOCKER
        mock_run.return_value = MagicMock(returncode=42)

        (tmp_path / "workspace").mkdir()
        config = _make_config()

        result = build_container(config, tmp_path)
        assert result == 42
