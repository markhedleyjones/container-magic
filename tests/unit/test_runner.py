"""Unit tests for container run logic.

Command execution model
-----------------------
Ad-hoc commands (no custom command match) use exec form - arguments are
passed directly to the container without shell wrapping. This matches
the behaviour of ``docker run``, ``kubectl exec``, and ``ssh``:

    cm run printenv WORKSPACE     -> ["printenv", "WORKSPACE"]  (exec form)
    cm run python script.py       -> ["python", "script.py"]    (exec form)
    cm run echo "hello world"     -> ["echo", "hello world"]    (exec form)

Users who need shell features (pipes, &&, variable expansion) must
explicitly invoke a shell, exactly as they would with docker run:

    cm run bash -c "ls | grep x"  -> ["bash", "-c", "ls | grep x"]

Custom commands defined in cm.yaml use ``bash -c`` because the command
field is a shell string that may contain pipes or other metacharacters.

This design was chosen over shell wrapping (``bash -c`` with
``shlex.join``) because shell wrapping creates ambiguous quoting: a
single argument like ``"printenv WORKSPACE"`` could be a shell command
string or a path with spaces, and there is no way to distinguish them.
Exec form avoids this entirely by not interpreting arguments at all.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch


from container_magic.core.config import ContainerMagicConfig, CustomCommand
from container_magic.core.runner import (
    _build_feature_flags,
    _detect_container_home,
    _detect_shell,
    _parse_mount_args,
    _parse_run_args,
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
        result = _detect_container_home()
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


class TestParseMountArgs:
    def _make_command(self, mounts=None):
        data = {"command": "test-cmd"}
        if mounts:
            data["mounts"] = mounts
        return CustomCommand(**data)

    def test_no_mounts(self):
        cmd = self._make_command()
        mounts, remaining = _parse_mount_args(cmd, ["--flag", "value"])
        assert mounts == {}
        assert remaining == ["--flag", "value"]

    def test_ro_mount_parsed(self):
        cmd = self._make_command(mounts={"model": "ro"})
        mounts, remaining = _parse_mount_args(
            cmd, ["model=/path/to/model", "--verbose"]
        )
        assert mounts == {"model": "/path/to/model"}
        assert remaining == ["--verbose"]

    def test_rw_mount_parsed(self):
        cmd = self._make_command(
            mounts={"results": {"mode": "rw", "prefix": "--output="}}
        )
        mounts, remaining = _parse_mount_args(cmd, ["results=/tmp/out", "extra"])
        assert mounts == {"results": "/tmp/out"}
        assert remaining == ["extra"]

    def test_mixed_mounts_and_remaining(self):
        cmd = self._make_command(mounts={"data": "ro", "logs": "rw"})
        mounts, remaining = _parse_mount_args(
            cmd, ["data=/input", "logs=/output", "--flag"]
        )
        assert mounts == {"data": "/input", "logs": "/output"}
        assert remaining == ["--flag"]

    def test_unknown_name_value_stays_in_remaining(self):
        cmd = self._make_command(mounts={"data": "ro"})
        mounts, remaining = _parse_mount_args(cmd, ["unknown=value", "data=/input"])
        assert mounts == {"data": "/input"}
        assert remaining == ["unknown=value"]


class TestParseRunArgs:
    def test_no_args(self):
        detach, passthrough, remaining = _parse_run_args([])
        assert detach is False
        assert passthrough == []
        assert remaining == []

    def test_detach_flag(self):
        detach, passthrough, remaining = _parse_run_args(["--detach", "slam"])
        assert detach is True
        assert passthrough == []
        assert remaining == ["slam"]

    def test_detach_short(self):
        detach, passthrough, remaining = _parse_run_args(["-d", "slam"])
        assert detach is True
        assert remaining == ["slam"]

    def test_no_separator(self):
        detach, passthrough, remaining = _parse_run_args(["slam", "--verbose"])
        assert detach is False
        assert passthrough == []
        assert remaining == ["slam", "--verbose"]

    def test_runtime_passthrough(self):
        detach, passthrough, remaining = _parse_run_args(["-e", "DOG=9", "--", "slam"])
        assert detach is False
        assert passthrough == ["-e", "DOG=9"]
        assert remaining == ["slam"]

    def test_multiple_passthrough_flags(self):
        detach, passthrough, remaining = _parse_run_args(
            ["-e", "DEBUG=1", "-v", "/tmp:/data", "--", "slam", "--verbose"]
        )
        assert passthrough == ["-e", "DEBUG=1", "-v", "/tmp:/data"]
        assert remaining == ["slam", "--verbose"]

    def test_detach_with_passthrough(self):
        detach, passthrough, remaining = _parse_run_args(
            ["-d", "-e", "DOG=9", "--", "slam"]
        )
        assert detach is True
        assert passthrough == ["-e", "DOG=9"]
        assert remaining == ["slam"]

    def test_separator_only(self):
        detach, passthrough, remaining = _parse_run_args(["--", "slam"])
        assert passthrough == []
        assert remaining == ["slam"]

    def test_separator_with_no_command(self):
        detach, passthrough, remaining = _parse_run_args(["-e", "X=1", "--"])
        assert passthrough == ["-e", "X=1"]
        assert remaining == []


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
