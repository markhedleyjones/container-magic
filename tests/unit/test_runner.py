"""Unit tests for container run logic."""

from pathlib import Path
from unittest.mock import MagicMock, patch


from container_magic.core.config import ContainerMagicConfig, CustomCommand
from container_magic.core.runner import (
    _build_feature_flags,
    _detect_container_home,
    _detect_shell,
    _parse_io_args,
    _translate_workdir,
    clean_images,
    stop_container,
)


def _make_config(**overrides):
    """Create a minimal config for testing."""
    data = {
        "names": {"image": "test-project", "user": "nonroot"},
        "stages": {
            "base": {"from": "ubuntu:22.04"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
    }
    data.update(overrides)
    return ContainerMagicConfig(**data)


class TestDetectContainerHome:
    def test_returns_home_directory(self):
        config = _make_config()
        result = _detect_container_home(config)
        assert result == str(Path.home())


class TestDetectShell:
    def test_default_shell_from_base_image(self):
        config = _make_config()
        shell = _detect_shell(config)
        assert shell in ["/bin/bash", "/bin/sh"]

    def test_explicit_shell_override(self):
        config = _make_config(
            stages={
                "base": {"from": "ubuntu:22.04"},
                "development": {"from": "base", "shell": "/bin/zsh"},
                "production": {"from": "base"},
            }
        )
        shell = _detect_shell(config)
        assert shell == "/bin/zsh"

    def test_alpine_defaults_to_sh(self):
        config = _make_config(
            stages={
                "base": {"from": "alpine:3.18"},
                "development": {"from": "base"},
                "production": {"from": "base"},
            }
        )
        shell = _detect_shell(config)
        assert shell == "/bin/sh"


class TestBuildFeatureFlags:
    def test_no_features(self):
        config = _make_config()
        flags = _build_feature_flags(config)
        assert flags == {
            "display": False,
            "gpu": False,
            "audio": False,
            "aws_credentials": False,
        }

    def test_all_features(self):
        config = _make_config(
            runtime={"features": ["display", "gpu", "audio", "aws_credentials"]}
        )
        flags = _build_feature_flags(config)
        assert all(flags.values())

    def test_partial_features(self):
        config = _make_config(runtime={"features": ["gpu"]})
        flags = _build_feature_flags(config)
        assert flags["gpu"] is True
        assert flags["display"] is False
        assert flags["audio"] is False
        assert flags["aws_credentials"] is False


class TestTranslateWorkdir:
    def test_project_root(self):
        result = _translate_workdir(
            Path("/home/user/project"),
            Path("/home/user/project"),
            "/home/user",
        )
        assert result == "/home/user"

    def test_subdirectory(self):
        result = _translate_workdir(
            Path("/home/user/project"),
            Path("/home/user/project/workspace/src"),
            "/home/user",
        )
        assert result == "/home/user/workspace/src"

    def test_outside_project(self):
        result = _translate_workdir(
            Path("/home/user/project"),
            Path("/tmp/somewhere"),
            "/home/user",
        )
        assert result == "/home/user"

    def test_workspace_root(self):
        result = _translate_workdir(
            Path("/home/user/project"),
            Path("/home/user/project/workspace"),
            "/home/user",
        )
        assert result == "/home/user/workspace"


class TestParseIOArgs:
    def _make_command(self, inputs=None, outputs=None):
        data = {"command": "test-cmd"}
        if inputs:
            data["inputs"] = inputs
        if outputs:
            data["outputs"] = outputs
        return CustomCommand(**data)

    def test_no_io_specs(self):
        cmd = self._make_command()
        inputs, outputs, remaining = _parse_io_args(cmd, ["--flag", "value"])
        assert inputs == {}
        assert outputs == {}
        assert remaining == ["--flag", "value"]

    def test_input_parsed(self):
        cmd = self._make_command(inputs={"model": {"prefix": "--model="}})
        inputs, outputs, remaining = _parse_io_args(
            cmd, ["model=/path/to/model", "--verbose"]
        )
        assert inputs == {"model": "/path/to/model"}
        assert outputs == {}
        assert remaining == ["--verbose"]

    def test_output_parsed(self):
        cmd = self._make_command(outputs={"results": {"prefix": "--output="}})
        inputs, outputs, remaining = _parse_io_args(cmd, ["results=/tmp/out", "extra"])
        assert inputs == {}
        assert outputs == {"results": "/tmp/out"}
        assert remaining == ["extra"]

    def test_mixed_io_and_remaining(self):
        cmd = self._make_command(
            inputs={"data": {"prefix": ""}},
            outputs={"logs": {"prefix": ""}},
        )
        inputs, outputs, remaining = _parse_io_args(
            cmd, ["data=/input", "logs=/output", "--flag"]
        )
        assert inputs == {"data": "/input"}
        assert outputs == {"logs": "/output"}
        assert remaining == ["--flag"]

    def test_unknown_name_value_stays_in_remaining(self):
        cmd = self._make_command(inputs={"data": {"prefix": ""}})
        inputs, outputs, remaining = _parse_io_args(
            cmd, ["unknown=value", "data=/input"]
        )
        assert inputs == {"data": "/input"}
        assert remaining == ["unknown=value"]


class TestStopContainer:
    @patch("container_magic.core.runner.subprocess.run")
    @patch("container_magic.core.runner.get_runtime")
    def test_stop_running_container(self, mock_get_runtime, mock_run):
        from container_magic.core.runtime import Runtime

        mock_get_runtime.return_value = Runtime.PODMAN
        mock_run.return_value = MagicMock(returncode=0)

        config = _make_config()
        result = stop_container(config)

        assert result == 0
        calls = mock_run.call_args_list
        assert len(calls) == 2
        assert calls[0].args[0] == ["podman", "stop", "test-project-development"]
        assert calls[1].args[0] == ["podman", "rm", "test-project-development"]

    @patch("container_magic.core.runner.subprocess.run")
    @patch("container_magic.core.runner.get_runtime")
    def test_stop_not_running(self, mock_get_runtime, mock_run):
        from container_magic.core.runtime import Runtime

        mock_get_runtime.return_value = Runtime.PODMAN
        mock_run.return_value = MagicMock(returncode=1)

        config = _make_config()
        result = stop_container(config)

        assert result == 0  # Idempotent
        # Should still attempt rm even if stop fails
        calls = mock_run.call_args_list
        assert len(calls) == 2
        assert calls[1].args[0] == ["podman", "rm", "test-project-development"]


class TestCleanImages:
    @patch("container_magic.core.runner.subprocess.run")
    @patch("container_magic.core.runner.get_runtime")
    def test_removes_both_tags(self, mock_get_runtime, mock_run):
        from container_magic.core.runtime import Runtime

        mock_get_runtime.return_value = Runtime.DOCKER
        mock_run.return_value = MagicMock(returncode=0)

        config = _make_config()
        result = clean_images(config)

        assert result == 0
        calls = mock_run.call_args_list
        assert len(calls) == 2
        assert calls[0].args[0] == ["docker", "rmi", "test-project:development"]
        assert calls[1].args[0] == ["docker", "rmi", "test-project:latest"]

    @patch("container_magic.core.runner.subprocess.run")
    @patch("container_magic.core.runner.get_runtime")
    def test_no_images_to_remove(self, mock_get_runtime, mock_run):
        from container_magic.core.runtime import Runtime

        mock_get_runtime.return_value = Runtime.DOCKER
        mock_run.return_value = MagicMock(returncode=1)

        config = _make_config()
        result = clean_images(config)

        assert result == 0  # Idempotent
