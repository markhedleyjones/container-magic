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
    _add_mount_volumes,
    build_feature_flags,
    collect_env_files,
    _detect_container_home,
    _detect_shell,
    _parse_mount_args,
    _parse_run_args,
    _translate_workdir,
    clean_images,
    run_container,
    stop_container,
)


def _make_config(**overrides):
    """Create a minimal config for testing."""
    data = {
        "names": {"image": "test-project", "user": "nonroot"},
        "stages": {
            "base": {"from": "debian:bookworm-slim"},
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
            runtime={"shell": "/bin/zsh"},
        )
        shell = _detect_shell(config)
        assert shell == "/bin/zsh"

    def test_alpine_defaults_to_sh(self):
        config = _make_config(
            stages={
                "base": {"from": "alpine:latest"},
                "development": {"from": "base"},
                "production": {"from": "base"},
            }
        )
        shell = _detect_shell(config)
        assert shell == "/bin/sh"

    def test_distro_alpine_sets_shell(self):
        """distro: alpine on a non-alpine-named image should resolve to /bin/sh."""
        config = _make_config(
            stages={
                "base": {"from": "myimage:latest", "distro": "alpine"},
                "development": {"from": "base"},
                "production": {"from": "base"},
            }
        )
        shell = _detect_shell(config)
        assert shell == "/bin/sh"

    def test_runtime_shell_takes_precedence_over_distro(self):
        config = _make_config(
            runtime={"shell": "/bin/zsh"},
            stages={
                "base": {"from": "myimage:latest", "distro": "alpine"},
                "development": {"from": "base"},
                "production": {"from": "base"},
            },
        )
        shell = _detect_shell(config)
        assert shell == "/bin/zsh"


class TestBuildFeatureFlags:
    def test_no_features(self):
        config = _make_config()
        flags = build_feature_flags(config)
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
        flags = build_feature_flags(config)
        assert all(flags.values())

    def test_partial_features(self):
        config = _make_config(runtime={"features": ["gpu"]})
        flags = build_feature_flags(config)
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


class TestCollectEnvFiles:
    def test_no_env_files(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        assert collect_env_files(project) == []

    def test_env_in_project_dir_only(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        (project / ".env").write_text("KEY=value")
        result = collect_env_files(project)
        assert result == [project / ".env"]

    def test_env_in_parent_only(self, tmp_path):
        (tmp_path / ".env").write_text("KEY=parent")
        project = tmp_path / "project"
        project.mkdir()
        result = collect_env_files(project)
        assert result == [tmp_path / ".env"]

    def test_env_in_both_parent_and_project(self, tmp_path):
        (tmp_path / ".env").write_text("KEY=parent")
        project = tmp_path / "project"
        project.mkdir()
        (project / ".env").write_text("KEY=project")
        result = collect_env_files(project)
        assert result == [tmp_path / ".env", project / ".env"]

    def test_env_in_grandparent_and_project(self, tmp_path):
        (tmp_path / ".env").write_text("KEY=grandparent")
        mid = tmp_path / "mid"
        mid.mkdir()
        project = mid / "project"
        project.mkdir()
        (project / ".env").write_text("KEY=project")
        result = collect_env_files(project)
        assert result == [tmp_path / ".env", project / ".env"]


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


class TestAddMountVolumes:
    def _make_command(self, mounts=None):
        data = {"command": "test-cmd"}
        if mounts:
            data["mounts"] = mounts
        return CustomCommand(**data)

    def test_space_prefix_splits_into_separate_fragments(self, tmp_path):
        test_file = tmp_path / "input.txt"
        test_file.write_text("test")
        cmd = self._make_command(mounts={"data": {"mode": "ro", "prefix": "--data "}})
        args = []
        fragments, _ = _add_mount_volumes(args, cmd, {"data": str(test_file)})
        assert fragments == ["--data", f"/mnt/data/{test_file.name}"]

    def test_equals_prefix_stays_as_one_fragment(self, tmp_path):
        test_file = tmp_path / "input.txt"
        test_file.write_text("test")
        cmd = self._make_command(mounts={"data": {"mode": "ro", "prefix": "--data="}})
        args = []
        fragments, _ = _add_mount_volumes(args, cmd, {"data": str(test_file)})
        assert fragments == ["--data=/mnt/data/input.txt"]

    def test_no_prefix_produces_path_only(self, tmp_path):
        test_file = tmp_path / "input.txt"
        test_file.write_text("test")
        cmd = self._make_command(mounts={"data": {"mode": "ro"}})
        args = []
        fragments, _ = _add_mount_volumes(args, cmd, {"data": str(test_file)})
        assert fragments == [f"/mnt/data/{test_file.name}"]

    def test_rw_mount_with_space_prefix(self, tmp_path):
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        cmd = self._make_command(
            mounts={"results": {"mode": "rw", "prefix": "--output "}}
        )
        args = []
        fragments, _ = _add_mount_volumes(args, cmd, {"results": str(output_dir)})
        assert fragments == ["--output", "/mnt/results"]


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


def _mock_subprocess_run(returncode=0, stdout="", stderr=""):
    """Create a mock for subprocess.run with configurable return."""
    mock = MagicMock()
    mock.returncode = returncode
    mock.stdout = stdout
    mock.stderr = stderr
    return mock


class TestRunContainer:
    """Tests for run_container argument assembly."""

    def _run(self, config=None, user_args=None, project_dir=None, user_cwd=None):
        """Run run_container with mocks and return the captured run args."""
        if config is None:
            config = _make_config()
        if user_args is None:
            user_args = ["echo", "hello"]
        if project_dir is None:
            project_dir = Path("/tmp/test-project")
        if user_cwd is None:
            user_cwd = project_dir

        with (
            patch("container_magic.core.runner.subprocess.run") as mock_run,
            patch("container_magic.core.runner.get_runtime") as mock_runtime,
            patch(
                "container_magic.core.runner.scan_workspace_symlinks", return_value=[]
            ),
            patch("container_magic.core.runner.collect_env_files", return_value=[]),
            patch(
                "container_magic.core.runner._detect_container_home",
                return_value="/home/testuser",
            ),
            patch("container_magic.core.runner.sys.stdin") as mock_stdin,
        ):
            from container_magic.core.runtime import Runtime

            mock_runtime.return_value = Runtime.DOCKER
            mock_stdin.isatty.return_value = False

            mock_run.side_effect = [
                _mock_subprocess_run(returncode=0),  # image inspect
                _mock_subprocess_run(returncode=0, stdout=""),  # ps check
                _mock_subprocess_run(returncode=0),  # docker run
            ]

            run_container(config, project_dir, user_cwd, user_args)

            calls = mock_run.call_args_list
            for call in calls:
                args = call.args[0] if call.args else []
                if len(args) > 1 and args[1] == "run":
                    return args
            return calls[-1].args[0]

    def test_basic_args(self):
        args = self._run()
        assert args[0] == "docker"
        assert args[1] == "run"
        name_idx = args.index("--name")
        assert args[name_idx + 1] == "test-project-development"
        assert "test-project:development" in args

    def test_workspace_mount(self):
        args = self._run(project_dir=Path("/tmp/test-project"))
        volume_args = [args[i + 1] for i in range(len(args)) if args[i] == "-v"]
        workspace_mounts = [v for v in volume_args if "workspace" in v and ":z" in v]
        assert len(workspace_mounts) >= 1

    def test_workdir_set(self):
        args = self._run()
        assert "--workdir" in args

    def test_image_not_found_returns_1(self):
        config = _make_config()
        with (
            patch("container_magic.core.runner.subprocess.run") as mock_run,
            patch("container_magic.core.runner.get_runtime") as mock_runtime,
            patch(
                "container_magic.core.runner.scan_workspace_symlinks", return_value=[]
            ),
            patch("container_magic.core.runner.collect_env_files", return_value=[]),
            patch(
                "container_magic.core.runner._detect_container_home",
                return_value="/home/testuser",
            ),
        ):
            from container_magic.core.runtime import Runtime

            mock_runtime.return_value = Runtime.DOCKER
            mock_run.return_value = _mock_subprocess_run(returncode=1)

            result = run_container(config, Path("/tmp/test"), Path("/tmp/test"), [])
            assert result == 1

    def test_ipc_mode(self):
        config = _make_config(runtime={"ipc": "host"})
        args = self._run(config=config)
        ipc_idx = args.index("--ipc")
        assert args[ipc_idx + 1] == "host"

    def test_network_mode(self):
        config = _make_config(runtime={"network_mode": "host"})
        args = self._run(config=config)
        net_idx = args.index("--net")
        assert args[net_idx + 1] == "host"

    def test_privileged_mode(self):
        config = _make_config(runtime={"privileged": True})
        args = self._run(config=config)
        assert "--privileged" in args

    def test_volumes_expanded_and_labelled(self):
        config = _make_config(runtime={"volumes": ["/tmp/data:/data:ro"]})
        args = self._run(config=config)
        volume_args = [args[i + 1] for i in range(len(args)) if args[i] == "-v"]
        data_mounts = [v for v in volume_args if "/tmp/data" in v]
        assert len(data_mounts) == 1
        assert ":ro,z" in data_mounts[0]

    def test_devices_passthrough(self):
        config = _make_config(runtime={"devices": ["/dev/video0:/dev/video0"]})
        args = self._run(config=config)
        dev_idx = args.index("--device")
        assert args[dev_idx + 1] == "/dev/video0:/dev/video0"

    def test_ad_hoc_command_exec_form(self):
        args = self._run(user_args=["python3", "script.py"])
        assert "python3" in args
        assert "script.py" in args
        assert "-c" not in args

    def test_custom_command_shell_wrapped(self):
        config = _make_config(commands={"train": {"command": "python train.py"}})
        args = self._run(config=config, user_args=["train"])
        c_idx = args.index("-c")
        assert "python train.py" in args[c_idx + 1]

    def test_custom_command_env_vars(self):
        config = _make_config(
            commands={"train": {"command": "echo", "env": {"CUDA": "0"}}}
        )
        args = self._run(config=config, user_args=["train"])
        e_idx = args.index("-e")
        assert args[e_idx + 1] == "CUDA=0"

    def test_custom_command_ports(self):
        config = _make_config(
            commands={"serve": {"command": "echo", "ports": ["8000:8000"]}}
        )
        args = self._run(config=config, user_args=["serve"])
        pub_idx = args.index("--publish")
        assert args[pub_idx + 1] == "8000:8000"

    def test_detach_mode(self):
        config = _make_config()
        with (
            patch("container_magic.core.runner.subprocess.run") as mock_run,
            patch("container_magic.core.runner.get_runtime") as mock_runtime,
            patch(
                "container_magic.core.runner.scan_workspace_symlinks", return_value=[]
            ),
            patch("container_magic.core.runner.collect_env_files", return_value=[]),
            patch(
                "container_magic.core.runner._detect_container_home",
                return_value="/home/testuser",
            ),
        ):
            from container_magic.core.runtime import Runtime

            mock_runtime.return_value = Runtime.DOCKER
            mock_run.side_effect = [
                _mock_subprocess_run(returncode=0),  # image inspect
                _mock_subprocess_run(returncode=0),  # docker run (detach skips ps)
            ]

            run_container(
                config, Path("/tmp/test"), Path("/tmp/test"), ["--detach", "echo"]
            )

            run_call = mock_run.call_args_list[-1]
            args = run_call.args[0]
            assert "--detach" in args
