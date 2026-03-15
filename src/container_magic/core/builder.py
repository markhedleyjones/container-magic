"""Container build logic.

Reads cm.yaml and constructs docker/podman build commands.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import List

from container_magic.core.config import ContainerMagicConfig
from container_magic.core.runtime import get_runtime
from container_magic.core.steps import has_create_user_in_stages
from container_magic.core.symlinks import scan_workspace_symlinks


def build_container(
    config: ContainerMagicConfig,
    project_dir: Path,
    target: str = "development",
    tag: str = "",
) -> int:
    """Build a container image.

    Args:
        config: Loaded configuration.
        project_dir: Path to the project root (where cm.yaml lives).
        target: Dockerfile stage to build (default: "development").
        tag: Override the image tag.

    Returns:
        Exit code from the build process.
    """
    runtime = get_runtime(config.backend)
    runtime_cmd = runtime.value

    image_tag = tag or target
    image_name = config.names.image

    # Determine build args for user
    has_user = has_create_user_in_stages(config.stages)

    if target == "development":
        # Development uses the host user
        user_name = os.environ.get("USER", "nonroot")
        user_uid = str(os.getuid())
        user_gid = str(os.getgid())
    else:
        # All other targets use the configured user
        if has_user and config.names.user != "root":
            user_name = config.names.user
            user_uid = "1000"
            user_gid = "1000"
        else:
            user_name = "root"
            user_uid = "0"
            user_gid = "0"

    # Regenerate files before building
    from container_magic.generators.dockerfile import generate_dockerfile
    from container_magic.generators.build_script import generate_build_script
    from container_magic.generators.run_script import generate_run_script

    generate_dockerfile(config, project_dir / "Dockerfile")
    generate_build_script(config, project_dir)
    generate_run_script(config, project_dir)

    # Handle symlink staging for production builds
    staging_dir = project_dir / ".cm-cache" / "staging"
    workspace_symlinks = scan_workspace_symlinks(project_dir / config.names.workspace)

    if workspace_symlinks:
        # Clean and recreate staging directory
        if staging_dir.exists():
            shutil.rmtree(staging_dir)

        for rel_path in workspace_symlinks:
            src = project_dir / config.names.workspace / rel_path
            dest = staging_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            # cp -rL to dereference symlinks
            subprocess.run(
                ["cp", "-rL", str(src), str(dest)],
                check=True,
            )
            print(f"Staging symlink: {config.names.workspace}/{rel_path}")

    # Build command
    build_args: List[str] = [runtime_cmd, "build"]
    build_args.extend(["--target", target])
    build_args.extend(["--build-arg", f"USER_NAME={user_name}"])
    build_args.extend(["--build-arg", f"USER_UID={user_uid}"])
    build_args.extend(["--build-arg", f"USER_GID={user_gid}"])
    build_args.extend(["--build-arg", f"WORKSPACE_NAME={config.names.workspace}"])

    if target == "development":
        # Development: also pass USER_HOME
        user_home = os.path.expanduser("~")
        build_args.extend(["--build-arg", f"USER_HOME={user_home}"])

    build_args.extend(["--tag", f"{image_name}:{image_tag}"])
    build_args.append(".")

    print(f"Building image: {image_name}:{image_tag} (target: {target})")

    try:
        result = subprocess.run(build_args, cwd=project_dir)
        if result.returncode == 0:
            print(f"Image built successfully: {image_name}:{image_tag}")
        return result.returncode
    finally:
        # Clean up staging directory
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
