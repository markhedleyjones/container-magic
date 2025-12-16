"""Dockerfile generation from configuration."""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from jinja2 import Environment, PackageLoader, select_autoescape

from container_magic.core.cache import get_asset_cache_path
from container_magic.core.config import (
    ContainerMagicConfig,
    StageConfig,
    UserTargetConfig,
)
from container_magic.core.templates import (
    detect_package_manager,
    detect_shell,
    detect_user_creation_style,
)


def get_user_config(
    config: ContainerMagicConfig, target: str = "production"
) -> Optional[UserTargetConfig]:
    """Get the user configuration for a specific target (development or production), or None if not defined."""

    if config.user:
        if target == "development":
            return config.user.development
        elif target == "production":
            return config.user.production
    return None


def process_stage_steps(
    stage: StageConfig,
    stage_name: str,
    project_dir: Path,
    stages_dict: Dict[str, StageConfig],
    production_user: str,
    has_explicit_user_config: bool,
    workspace_name: str,
) -> Tuple[List[Dict], bool, List[Dict]]:
    """
    Process build steps for a stage.

    Returns:
        (ordered_steps, has_copy_cached_assets, cached_assets_data)
    """
    # Default build order if not specified
    if stage.steps is None:
        # For stages that inherit from another stage (not a Docker image),
        # default to empty steps (inherit everything from parent)
        # For base stages (from a Docker image), use default build steps
        if ":" in stage.frm or "/" in stage.frm:
            # FROM a Docker image - default build (only if user is configured)
            steps = [
                "install_system_packages",
                "install_pip_packages",
            ]
            if has_explicit_user_config:
                steps.append("create_user")
        else:
            # FROM another stage - minimal default (just inherits)
            steps = []
            # Production stage should copy workspace by default
            if stage_name == "production":
                steps = ["copy_workspace"]
    else:
        steps = stage.steps

    # Track what we find in steps
    has_create_user = False
    has_switch_user = False
    has_copy_cached_assets = False

    # Process steps into ordered sections
    ordered_steps = []
    for step in steps:
        if step == "install_system_packages":
            ordered_steps.append({"type": "system_packages"})
        elif step == "install_pip_packages":
            ordered_steps.append({"type": "pip_packages"})
        elif step == "create_user":
            ordered_steps.append({"type": "create_user"})
            has_create_user = True
        elif step == "switch_user":
            ordered_steps.append({"type": "switch_user"})
            has_switch_user = True
        elif step == "switch_root":
            ordered_steps.append({"type": "switch_root"})
        elif step == "copy_cached_assets":
            ordered_steps.append({"type": "cached_assets"})
            has_copy_cached_assets = True
        elif step == "copy_workspace":
            ordered_steps.append({"type": "copy_workspace"})
        else:
            # Custom RUN command
            ordered_steps.append({"type": "custom", "command": step})

    # Validation: Check if switch_user used but no create_user in this or parent stages
    if has_switch_user and not has_create_user:
        # Walk up the stage hierarchy to find if any parent has create_user
        user_created = False
        current_stage_name = stage_name
        visited = set()

        # Check parent stages
        if stage.frm in stages_dict:
            current_stage_name = stage.frm

            while not user_created and current_stage_name in stages_dict:
                if current_stage_name in visited:
                    break
                visited.add(current_stage_name)

                current_stage = stages_dict[current_stage_name]
                # Check if parent has create_user keyword OR uses default build steps from Docker image
                if current_stage.steps and "create_user" in current_stage.steps:
                    user_created = True
                    break
                # Check if parent uses default build steps (no steps specified and FROM a Docker image)
                if current_stage.steps is None and (
                    ":" in current_stage.frm or "/" in current_stage.frm
                ):
                    # Default build steps include create_user
                    user_created = True
                    break

                # Move to parent stage
                if current_stage.frm in stages_dict:
                    current_stage_name = current_stage.frm
                else:
                    break

        if not user_created:
            print(
                f"⚠️  Warning: Stage '{stage_name}' uses 'switch_user' but no 'create_user' found in this stage or parent stages",
                file=sys.stderr,
            )
            print("   The switch_user step may fail at build time.", file=sys.stderr)

    # Validation: Check if create_user or switch_user used but production.user not defined
    if (has_create_user or has_switch_user) and not has_explicit_user_config:
        raise ValueError(
            f"Stage '{stage_name}' uses 'create_user' or 'switch_user' but production.user is not defined. "
            "Define production.user in your configuration."
        )

    # Warn if cached_assets defined but copy_cached_assets not in steps
    if stage.cached_assets and not has_copy_cached_assets:
        print(
            f"⚠️  Warning: Stage '{stage_name}' has cached_assets but 'copy_cached_assets' not in steps",
            file=sys.stderr,
        )
        print(
            "   Assets will be downloaded but not copied into the image.",
            file=sys.stderr,
        )
        print("   Add 'copy_cached_assets' to steps to use them.", file=sys.stderr)

    # Prepare cached assets data
    cached_assets_data = []
    for asset in stage.cached_assets:
        asset_dir, asset_file = get_asset_cache_path(project_dir, asset.url)
        # Store relative path from Dockerfile location to cache
        rel_path = asset_file.relative_to(project_dir)
        cached_assets_data.append(
            {"source": str(rel_path), "dest": asset.dest, "url": asset.url}
        )

    return ordered_steps, has_copy_cached_assets, cached_assets_data


def generate_dockerfile(config: ContainerMagicConfig, output_path: Path) -> None:
    """
    Generate Dockerfile from configuration.

    Args:
        config: Container-magic configuration
        output_path: Path to write Dockerfile
    """
    env = Environment(
        loader=PackageLoader("container_magic", "templates"),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )

    template = env.get_template("Dockerfile.j2")

    # Build stages dict with defaults if needed
    stages = dict(config.stages)

    # Add default development stage if missing
    if "development" not in stages:
        from container_magic.core.config import StageConfig

        stages["development"] = StageConfig(frm="base", steps=["switch_user"])

    # Add default production stage if missing
    if "production" not in stages:
        from container_magic.core.config import StageConfig

        stages["production"] = StageConfig(frm="base")

    # Get user config
    user_cfg = get_user_config(config)

    # Process all stages
    stages_data = []
    for stage_name, stage_config in stages.items():
        # Auto-detect package manager and shell if not specified
        # For non-base stages, try to detect from their base image
        base_image = stage_config.frm
        package_manager = stage_config.package_manager or detect_package_manager(
            base_image
        )
        shell = stage_config.shell or detect_shell(base_image)
        user_creation_style = detect_user_creation_style(base_image)

        # Process build steps
        has_explicit_user = user_cfg is not None
        user_name = user_cfg.name if user_cfg else "root"
        ordered_steps, has_copy_cached_assets, cached_assets_data = process_stage_steps(
            stage_config,
            stage_name,
            output_path.parent,
            stages,
            user_name,
            has_explicit_user,
            config.project.workspace,
        )

        # Check if this stage needs USER ARG definitions
        # ARGs don't persist across stages in Docker, so each stage needs them
        # Skip if user is not explicitly configured or if user is root
        needs_user_args = user_cfg is not None and user_cfg.name != "root"

        stages_data.append(
            {
                "name": stage_name,
                "from": base_image,
                "apt_packages": stage_config.packages.apt,
                "pip_packages": stage_config.packages.pip,
                "env_vars": stage_config.env,
                "cached_assets": cached_assets_data,
                "package_manager": package_manager,
                "shell": shell,
                "user_creation_style": user_creation_style,
                "user": user_name,
                "user_uid": (user_cfg.uid or 1000) if user_cfg else 0,
                "user_gid": (user_cfg.gid or 1000) if user_cfg else 0,
                "user_home": (user_cfg.home or f"/home/{user_cfg.name}")
                if user_cfg
                else "/root",
                "ordered_steps": ordered_steps,
                "needs_user_args": needs_user_args,
            }
        )

    dockerfile_content = template.render(
        stages=stages_data,
        workspace_name=config.project.workspace,
    )

    with open(output_path, "w") as f:
        f.write(dockerfile_content)
