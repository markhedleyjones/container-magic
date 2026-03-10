"""Container run logic.

Reads cm.yaml and constructs docker/podman run commands.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from container_magic.core.config import ContainerMagicConfig, CustomCommand
from container_magic.core.runtime import Runtime, get_runtime
from container_magic.core.symlinks import scan_workspace_symlinks
from container_magic.core.templates import detect_shell, resolve_base_image


def _detect_container_home(config: ContainerMagicConfig) -> str:
    """Determine the container home directory for development.

    Development builds use the host user's UID/GID, so the home directory
    matches the host user's home.
    """
    return os.path.expanduser("~")


def _detect_shell(config: ContainerMagicConfig) -> str:
    """Detect the shell for the development stage."""
    dev_stage = "development" if "development" in config.stages else "base"
    dev_stage_config = config.stages[dev_stage]
    return dev_stage_config.shell or detect_shell(
        resolve_base_image(dev_stage_config.frm, config.stages)
    )


def _build_feature_flags(config: ContainerMagicConfig) -> Dict[str, bool]:
    """Build feature flags dict from runtime config."""
    runtime_features = config.runtime.features if config.runtime else []
    return {
        "display": "display" in runtime_features,
        "gpu": "gpu" in runtime_features,
        "audio": "audio" in runtime_features,
        "aws_credentials": "aws_credentials" in runtime_features,
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


def _parse_io_args(
    command_spec: CustomCommand, user_args: List[str]
) -> Tuple[Dict[str, str], Dict[str, str], List[str]]:
    """Parse name=value arguments for command inputs and outputs.

    Returns:
        Tuple of (inputs dict, outputs dict, remaining args).
        Each dict maps the IO name to the user-provided host path.
    """
    input_names = set(command_spec.inputs.keys())
    output_names = set(command_spec.outputs.keys())
    inputs = {}
    outputs = {}
    remaining = []

    for arg in user_args:
        if "=" in arg:
            name, _, value = arg.partition("=")
            if name in input_names:
                inputs[name] = value
                continue
            elif name in output_names:
                outputs[name] = value
                continue
        remaining.append(arg)

    return inputs, outputs, remaining


def _add_io_mounts(
    args: List[str],
    command_spec: CustomCommand,
    inputs: Dict[str, str],
    outputs: Dict[str, str],
) -> Tuple[List[str], List[str]]:
    """Add input/output bind mounts and build command fragments.

    Returns:
        Tuple of (command fragments to append, manifest lines).
    """
    command_fragments = []
    manifest_lines = []

    for name, host_path in inputs.items():
        host_path = os.path.expanduser(host_path)
        resolved = os.path.realpath(host_path)

        if not os.path.exists(resolved):
            print(f"Error: Input '{name}' not found: {host_path}", file=sys.stderr)
            sys.exit(1)

        basename = os.path.basename(resolved)
        container_path = f"/mnt/inputs/{name}/{basename}"

        args.extend(["-v", f"{resolved}:{container_path}:ro,z"])
        manifest_lines.append(f"{resolved}:{container_path}")

        spec = command_spec.inputs[name]
        command_fragments.append(f"{spec.prefix}{container_path}")

    for name, host_path in outputs.items():
        host_path = os.path.expanduser(host_path)
        resolved = os.path.realpath(host_path)

        # Create output directory if it does not exist
        os.makedirs(resolved, exist_ok=True)

        container_path = f"/mnt/outputs/{name}"

        args.extend(["-v", f"{resolved}:{container_path}:rw,z"])
        manifest_lines.append(f"{resolved}:{container_path}")

        spec = command_spec.outputs[name]
        command_fragments.append(f"{spec.prefix}{container_path}")

    return command_fragments, manifest_lines


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
    shell = _detect_shell(config)
    container_home = _detect_container_home(config)
    features = _build_feature_flags(config)
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

    # Parse detach flag
    detach = False
    args_remaining = list(user_args)
    if args_remaining and args_remaining[0] in ("--detach", "-d"):
        detach = True
        args_remaining.pop(0)

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

    if config.runtime.ipc:
        run_args.extend(["--ipc", config.runtime.ipc])
    if config.runtime.network_mode:
        run_args.extend(["--net", config.runtime.network_mode])

    if runtime == Runtime.PODMAN:
        run_args.append("--replace")
        run_args.append("--userns=keep-id")
        run_args.append("--env-host=false")

    if config.runtime.privileged:
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

    # Load .env file
    env_file = project_dir / ".env"
    if env_file.is_file():
        run_args.extend(["--env-file", str(env_file)])

    # Additional volumes
    for volume in config.runtime.volumes:
        run_args.extend(["-v", volume])

    # Device passthrough
    for device in config.runtime.devices:
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

    # Handle custom command with inputs/outputs
    manifest_file = None
    command_str = None

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

        # Parse input/output arguments
        io_inputs, io_outputs, extra_args = _parse_io_args(command_spec, args_remaining)

        # Add mounts and build command
        command_fragments, manifest_lines = _add_io_mounts(
            run_args, command_spec, io_inputs, io_outputs
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

        # Build full command string
        parts = [command_spec.command]
        parts.extend(command_fragments)
        parts.extend(extra_args)
        command_str = " ".join(parts)

    else:
        # No custom command - use user args as command or open shell
        if args_remaining:
            command_str = " ".join(args_remaining)

    # Working directory
    workdir = _translate_workdir(project_dir, user_cwd, container_home)
    run_args.extend(["--workdir", workdir])

    # Detach mode
    if detach:
        run_args.append("--detach")
        run_args.append(image)
        if command_str:
            run_args.extend([shell, "-c", command_str])
        else:
            run_args.append(shell)

        try:
            result = subprocess.run(run_args)
            return result.returncode
        finally:
            _cleanup(manifest_file, xhost_cleanup)

    # Interactive mode
    if not command_str and sys.stdin.isatty():
        run_args.extend(["--interactive", "--tty"])

    run_args.append(image)

    if command_str:
        run_args.extend([shell, "-c", command_str])
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
            if not command_str and sys.stdin.isatty():
                exec_args.extend(["--interactive", "--tty"])
            exec_args.append(container_name)
            if command_str:
                exec_args.extend([shell, "-c", command_str])
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
    features = _build_feature_flags(config)
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
