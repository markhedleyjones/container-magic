"""Container run logic.

Reads cm.yaml and constructs docker/podman run commands.
"""

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from container_magic.core.config import (
    ContainerMagicConfig,
    CustomCommand,
    RuntimeConfig,
)
from container_magic.core.runtime import Runtime, get_runtime
from container_magic.core.symlinks import scan_workspace_symlinks
from container_magic.core.templates import (
    detect_shell,
    resolve_base_image,
    resolve_distro_shell,
)
from container_magic.core.volumes import (
    VolumeContext,
    expand_mount_path,
    expand_volumes_for_run,
    label_volumes,
    shorthand_names,
)


def collect_env_files(project_dir: Path) -> List[Path]:
    """Walk parent directories collecting .env files.

    Returns paths ordered most distant first, so that closer .env files
    are loaded last and their values take precedence with --env-file.
    """
    env_files = []
    search_dir = project_dir.resolve()
    while True:
        candidate = search_dir / ".env"
        if candidate.is_file():
            env_files.append(candidate)
        parent = search_dir.parent
        if parent == search_dir:
            break
        search_dir = parent
    env_files.reverse()
    return env_files


def _detect_container_home() -> str:
    """Determine the container home directory for development.

    Development builds use the host user's UID/GID, so the home directory
    matches the host user's home.
    """
    return os.path.expanduser("~")


def _detect_shell(
    config: ContainerMagicConfig, runtime_override: RuntimeConfig = None
) -> str:
    """Detect the interactive shell for cm run.

    Priority: runtime.shell > distro field > image-name detection.
    """
    rt = runtime_override or config.runtime
    runtime_shell = rt.shell
    if runtime_shell:
        return runtime_shell
    dev_stage = "development" if "development" in config.stages else "base"
    distro_shell = resolve_distro_shell(dev_stage, config.stages)
    if distro_shell:
        return distro_shell
    dev_stage_config = config.stages[dev_stage]
    return detect_shell(resolve_base_image(dev_stage_config.frm, config.stages))


def build_feature_flags(runtime: RuntimeConfig) -> Dict[str, bool]:
    """Build feature flags dict from a runtime config."""
    features = runtime.features
    return {
        "display": "display" in features,
        "gpu": "gpu" in features,
        "audio": "audio" in features,
        "aws_credentials": "aws_credentials" in features,
    }


def _add_display_args(args: List[str], runtime: Runtime) -> Optional[str]:
    """Add display (Wayland/X11) arguments. Returns xauth tempfile path if created."""
    xauth_file = None

    wayland_display = os.environ.get("WAYLAND_DISPLAY")
    if wayland_display:
        xdg_runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "")
        wayland_socket = f"{xdg_runtime_dir}/{wayland_display}"
        args.extend(["-e", "WAYLAND_DISPLAY"])
        args.extend(["-e", f"XDG_RUNTIME_DIR={xdg_runtime_dir}"])
        args.extend(["-v", f"{wayland_socket}:{wayland_socket}"])

    display = os.environ.get("DISPLAY")
    if display:
        xsock = "/tmp/.X11-unix"

        if runtime == Runtime.PODMAN:
            args.append("--security-opt=label=disable")
            xauth_file = "/tmp/.docker.xauth"
            # Create xauth file
            Path(xauth_file).touch()
            xauthority = Path.home() / ".Xauthority"
            if xauthority.is_file():
                try:
                    nlist = subprocess.run(
                        ["xauth", "nlist", display],
                        capture_output=True,
                    )
                    if nlist.stdout:
                        modified = nlist.stdout.replace(nlist.stdout[:4], b"ffff", 1)
                        subprocess.run(
                            ["xauth", "-f", xauth_file, "nmerge", "-"],
                            input=modified,
                            capture_output=True,
                        )
                except FileNotFoundError:
                    pass
            args.extend(["-e", f"XAUTHORITY={xauth_file}"])
            args.extend(["-v", f"{xauth_file}:{xauth_file}"])
        else:
            # Docker: use xhost
            try:
                subprocess.run(
                    ["xhost", "+local:"],
                    capture_output=True,
                )
            except FileNotFoundError:
                pass

        args.extend(["-e", "DISPLAY"])
        args.extend(["-v", f"{xsock}:{xsock}"])
        args.extend(["--env", "QT_X11_NO_MITSHM=1"])

    return xauth_file


def _add_gpu_args(args: List[str], runtime: Runtime) -> None:
    """Add GPU passthrough arguments."""
    if Path("/dev/dri").is_dir():
        args.extend(["--device", "/dev/dri:/dev/dri"])

    if shutil.which("nvidia-smi"):
        args.extend(["-e", "NVIDIA_DRIVER_CAPABILITIES=all"])
        if runtime == Runtime.DOCKER:
            args.append("--gpus=all")
        elif runtime == Runtime.PODMAN:
            args.extend(["--device", "nvidia.com/gpu=all"])
            args.append("--annotation=run.oci.keep_original_groups=1")
            if "--security-opt=label=disable" not in args:
                args.append("--security-opt=label=disable")


def _add_audio_args(args: List[str]) -> None:
    """Add audio (PulseAudio/PipeWire) arguments."""
    uid = os.getuid()
    pulse_socket = f"/run/user/{uid}/pulse/native"
    if Path(pulse_socket).is_socket():
        args.extend(["-v", f"{pulse_socket}:{pulse_socket}"])
        args.extend(["-e", f"PULSE_SERVER=unix:{pulse_socket}"])


def _add_aws_args(args: List[str], container_home: str) -> None:
    """Add AWS credentials mount."""
    aws_dir = Path.home() / ".aws"
    if aws_dir.is_dir():
        args.extend(["-v", f"{aws_dir}:{container_home}/.aws:z"])


def _parse_mount_args(
    command_spec: CustomCommand, user_args: List[str]
) -> Tuple[Dict[str, str], List[str]]:
    """Parse name=value arguments for command mounts.

    Returns:
        Tuple of (mounts dict, remaining args).
        The dict maps mount name to the user-provided host path.
    """
    mount_names = set(command_spec.mounts.keys())
    mounts = {}
    remaining = []

    for arg in user_args:
        if "=" in arg:
            name, _, value = arg.partition("=")
            if name in mount_names:
                mounts[name] = value
                continue
        remaining.append(arg)

    return mounts, remaining


def _add_mount_volumes(
    args: List[str],
    command_spec: CustomCommand,
    mounts: Dict[str, str],
    volume_context: Optional[VolumeContext] = None,
) -> Tuple[List[str], List[str]]:
    """Add bind mount volumes and build command fragments.

    Returns:
        Tuple of (command fragments to append, manifest lines).
    """
    command_fragments = []
    manifest_lines = []

    for name, host_path in mounts.items():
        if volume_context:
            host_path = expand_mount_path(host_path, volume_context)
        else:
            host_path = os.path.expanduser(host_path)
        resolved = os.path.realpath(host_path)
        spec = command_spec.mounts[name]

        if spec.mode == "ro":
            if not os.path.exists(resolved):
                print(f"Error: Mount '{name}' not found: {host_path}", file=sys.stderr)
                sys.exit(1)
            basename = os.path.basename(resolved)
            container_path = f"/mnt/{name}/{basename}"
            args.extend(["-v", f"{resolved}:{container_path}:ro,z"])
        else:
            os.makedirs(resolved, exist_ok=True)
            container_path = f"/mnt/{name}"
            args.extend(["-v", f"{resolved}:{container_path}:z"])

        manifest_lines.append(f"{resolved}:{container_path}")
        if spec.prefix and spec.prefix != spec.prefix.rstrip():
            prefix_parts = spec.prefix.rstrip().split()
            command_fragments.extend(prefix_parts + [container_path])
        else:
            command_fragments.append(f"{spec.prefix}{container_path}")

    return command_fragments, manifest_lines


def _parse_run_args(
    user_args: List[str],
) -> Tuple[bool, List[str], List[str]]:
    """Parse cm run arguments into detach flag, runtime passthrough, and remaining args.

    Args:
        user_args: Raw arguments from the command line.

    Returns:
        Tuple of (detach, runtime_passthrough, remaining_args).
    """
    args = list(user_args)

    # Parse detach flag
    detach = False
    if args and args[0] in ("--detach", "-d"):
        detach = True
        args.pop(0)

    # Parse runtime passthrough args (everything before --)
    runtime_passthrough = []
    if "--" in args:
        sep_idx = args.index("--")
        runtime_passthrough = args[:sep_idx]
        args = args[sep_idx + 1 :]

    return detach, runtime_passthrough, args


def _translate_workdir(project_dir: Path, user_cwd: Path, container_home: str) -> str:
    """Translate user's current working directory to container workdir."""
    try:
        rel_path = user_cwd.relative_to(project_dir)
        if str(rel_path) == ".":
            return container_home
        return f"{container_home}/{rel_path}"
    except ValueError:
        return container_home


def run_container(
    config: ContainerMagicConfig,
    project_dir: Path,
    user_cwd: Path,
    user_args: List[str],
) -> int:
    """Run a container using the development image.

    Args:
        config: Loaded configuration.
        project_dir: Path to the project root (where cm.yaml lives).
        user_cwd: User's current working directory.
        user_args: Arguments from the command line.

    Returns:
        Exit code from the container process.
    """
    runtime = get_runtime(config.backend)
    runtime_cmd = runtime.value
    effective_rt = config.effective_runtime("development")
    shell = _detect_shell(config, effective_rt)
    container_home = _detect_container_home()
    features = build_feature_flags(effective_rt)
    image = f"{config.names.image}:development"
    container_name = f"{config.names.image}-development"

    # Check image exists
    check = subprocess.run(
        [runtime_cmd, "image", "inspect", image],
        capture_output=True,
    )
    if check.returncode != 0:
        print(f"Error: Image {image} not found locally", file=sys.stderr)
        print("Build it with: cm build", file=sys.stderr)
        return 1

    # Parse flags and runtime passthrough
    detach, runtime_passthrough, args_remaining = _parse_run_args(user_args)

    # Check for custom command
    command_name = None
    command_spec = None
    if args_remaining and config.commands and args_remaining[0] in config.commands:
        command_name = args_remaining.pop(0)
        command_spec = config.commands[command_name]

    # Build run arguments
    run_args = [runtime_cmd, "run"]
    run_args.extend(["--name", container_name])
    run_args.extend(["--hostname", config.names.image])
    run_args.append("--rm")

    if effective_rt.ipc:
        run_args.extend(["--ipc", effective_rt.ipc])
    if effective_rt.network_mode:
        run_args.extend(["--net", effective_rt.network_mode])

    if runtime == Runtime.PODMAN:
        run_args.append("--replace")
        run_args.append("--userns=keep-id")
        run_args.append("--env-host=false")

    if effective_rt.privileged:
        run_args.append("--privileged")

    # Mount workspace
    workspace_name = config.names.workspace
    workspace_host = project_dir / workspace_name
    run_args.extend(
        [
            "-v",
            f"{workspace_host}:{container_home}/{workspace_name}:z",
        ]
    )

    # Symlink mounts
    workspace_symlinks = scan_workspace_symlinks(workspace_host)
    for rel_path in workspace_symlinks:
        run_args.extend(
            [
                "-v",
                f"{workspace_host}/{rel_path}:{container_home}/{workspace_name}/{rel_path}:z",
            ]
        )

    # Load .env files (walk parent directories, most distant first so closer values win)
    for env_file in collect_env_files(project_dir):
        run_args.extend(["--env-file", str(env_file)])

    # Create host folders for shorthand volumes before docker mounts them
    for name in shorthand_names(effective_rt.volumes):
        (project_dir / name).mkdir(parents=True, exist_ok=True)

    # Additional volumes (with variable expansion)
    volume_context = VolumeContext(
        user_home=os.path.expanduser("~"),
        container_home=container_home,
        workspace_user=str(project_dir / config.names.workspace),
        workspace_container=f"{container_home}/{config.names.workspace}",
        project_dir=str(project_dir),
    )
    expanded_volumes = expand_volumes_for_run(effective_rt.volumes, volume_context)
    labelled_volumes = label_volumes(expanded_volumes)
    for volume in labelled_volumes:
        run_args.extend(["-v", volume])

    # Device passthrough
    for device in effective_rt.devices:
        run_args.extend(["--device", device])

    # Feature flags
    xhost_cleanup = False
    if features["display"]:
        xauth = _add_display_args(run_args, runtime)
        if (
            not detach
            and not xauth
            and runtime == Runtime.DOCKER
            and os.environ.get("DISPLAY")
        ):
            xhost_cleanup = True

    if features["gpu"]:
        _add_gpu_args(run_args, runtime)

    if features["audio"]:
        _add_audio_args(run_args)

    if features["aws_credentials"]:
        _add_aws_args(run_args, container_home)

    # Runtime passthrough args (from -- separator)
    if runtime_passthrough:
        run_args.extend(runtime_passthrough)

    # Handle custom command with mounts
    manifest_file = None
    command_str = None
    parsed_mounts = {}

    if command_spec:
        # Use command-specific overrides if present
        if command_spec.ipc:
            # Remove runtime-level ipc if present and replace with command override
            if "--ipc" in run_args:
                idx = run_args.index("--ipc")
                run_args[idx + 1] = command_spec.ipc
            else:
                run_args.extend(["--ipc", command_spec.ipc])

        # Command environment variables
        for key, value in command_spec.env.items():
            run_args.extend(["-e", f"{key}={value}"])

        # Command ports
        for port in command_spec.ports:
            run_args.extend(["--publish", port])

        parsed_mounts, extra_args = _parse_mount_args(command_spec, args_remaining)
        command_fragments, manifest_lines = _add_mount_volumes(
            run_args, command_spec, parsed_mounts, volume_context
        )

        # Create manifest file if there are any mounts
        if manifest_lines:
            manifest_file = tempfile.NamedTemporaryFile(
                mode="w", prefix="cm-manifest-", delete=False
            )
            manifest_file.write("\n".join(manifest_lines) + "\n")
            manifest_file.close()
            run_args.extend(
                [
                    "-v",
                    f"{manifest_file.name}:/run/cm/mounts:ro,z",
                ]
            )

        # Build full command string: keep base command as-is (may contain
        # shell metacharacters like pipes) and quote extra arguments
        extra_parts = command_fragments + extra_args
        if extra_parts:
            command_str = command_spec.command + " " + shlex.join(extra_parts)
        else:
            command_str = command_spec.command

    else:
        # No custom command - pass args directly (exec form, no shell wrapping).
        # This matches docker run behaviour. Users who need shell features
        # (pipes, &&, variable expansion) use: cm run bash -c "..."
        pass

    # Working directory
    workdir = _translate_workdir(project_dir, user_cwd, container_home)
    run_args.extend(["--workdir", workdir])

    # Determine how to append the command to run_args:
    # - Custom command (command_str set): shell -c wrapping (command is a shell string)
    # - Ad-hoc with args: exec form (args passed directly, no shell)
    # - No command: interactive shell
    has_command = command_str or (not command_spec and args_remaining)

    # Detach mode
    if detach:
        run_args.append("--detach")
        run_args.append(image)
        if command_str:
            run_args.extend([shell, "-c", command_str])
        elif args_remaining and not command_spec:
            run_args.extend(args_remaining)
        else:
            run_args.append(shell)

        try:
            result = subprocess.run(run_args)
            return result.returncode
        finally:
            _cleanup(manifest_file, xhost_cleanup)

    # Interactive mode (only when no command at all)
    if not has_command and sys.stdin.isatty():
        run_args.extend(["--interactive", "--tty"])

    run_args.append(image)

    if command_str:
        run_args.extend([shell, "-c", command_str])
    elif args_remaining and not command_spec:
        run_args.extend(args_remaining)
    else:
        run_args.append(shell)

    # Check if container is already running
    ps_result = subprocess.run(
        [runtime_cmd, "ps", "--quiet", "--filter", f"name=^{container_name}$"],
        capture_output=True,
        text=True,
    )

    try:
        if ps_result.stdout.strip():
            # Exec into running container
            exec_args = [runtime_cmd, "exec"]
            exec_args.extend(["--workdir", workdir])

            # Forward command-specific env vars
            if command_spec:
                for key, value in command_spec.env.items():
                    exec_args.extend(["-e", f"{key}={value}"])

                # Warn about mounts/ports that can't be added to a running container
                if parsed_mounts:
                    print(
                        "Warning: Mounts cannot be added to a running container. "
                        "Stop the container first with 'cm stop'.",
                        file=sys.stderr,
                    )
                if command_spec.ports:
                    print(
                        "Warning: Ports cannot be added to a running container. "
                        "Stop the container first with 'cm stop'.",
                        file=sys.stderr,
                    )

            if not has_command and sys.stdin.isatty():
                exec_args.extend(["--interactive", "--tty"])
            exec_args.append(container_name)
            if command_str:
                exec_args.extend([shell, "-c", command_str])
            elif args_remaining and not command_spec:
                exec_args.extend(args_remaining)
            else:
                exec_args.append(shell)
            result = subprocess.run(exec_args)
            return result.returncode
        else:
            result = subprocess.run(run_args)
            return result.returncode
    finally:
        _cleanup(manifest_file, xhost_cleanup)


def stop_container(config: ContainerMagicConfig) -> int:
    """Stop the running development container.

    Returns:
        Exit code (always 0, stop is idempotent).
    """
    runtime = get_runtime(config.backend)
    runtime_cmd = runtime.value
    container_name = f"{config.names.image}-development"

    result = subprocess.run(
        [runtime_cmd, "stop", container_name],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print(f"Stopped {container_name}")
    else:
        print(f"Container {container_name} is not running")

    # Remove container (handles cases where --rm didn't fire, e.g. SIGKILL)
    subprocess.run(
        [runtime_cmd, "rm", container_name],
        capture_output=True,
        text=True,
    )

    # xhost cleanup if display feature enabled with Docker
    features = build_feature_flags(config.effective_runtime("development"))
    if features["display"] and runtime == Runtime.DOCKER and os.environ.get("DISPLAY"):
        try:
            subprocess.run(["xhost", "-local:"], capture_output=True)
        except FileNotFoundError:
            pass

    return 0


def clean_images(config: ContainerMagicConfig) -> int:
    """Remove container images for this project.

    Returns:
        Exit code (always 0, clean is idempotent).
    """
    runtime = get_runtime(config.backend)
    runtime_cmd = runtime.value
    image_name = config.names.image

    removed = []
    for tag in ["development", "latest"]:
        image = f"{image_name}:{tag}"
        result = subprocess.run(
            [runtime_cmd, "rmi", image],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            removed.append(image)

    if removed:
        for img in removed:
            print(f"Removed {img}")
    else:
        print("No images to remove")

    return 0


def _cleanup(manifest_file, xhost_cleanup: bool) -> None:
    """Clean up temporary resources."""
    if manifest_file:
        try:
            os.unlink(manifest_file.name)
        except OSError:
            pass

    if xhost_cleanup:
        try:
            subprocess.run(
                ["xhost", "-local:"],
                capture_output=True,
            )
        except FileNotFoundError:
            pass
