"""Dockerfile generation from configuration."""

import sys
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from container_magic.core.cache import get_asset_cache_path
from container_magic.core.config import ContainerMagicConfig, StageConfig
from container_magic.core.templates import (
    detect_package_manager,
    detect_shell,
    detect_user_creation_style,
)


def process_stage_build_steps(
    stage: StageConfig,
    stage_name: str,
    project_dir: Path,
    stages_dict: dict[str, StageConfig],
) -> tuple[list[dict], bool, list[dict]]:
    """
    Process build steps for a stage.

    Returns:
        (ordered_steps, has_copy_cached_assets, cached_assets_data)
    """
    # Default build order if not specified
    if stage.build_steps is None:
        # For stages that inherit from another stage (not a Docker image),
        # default to empty build_steps (inherit everything from parent)
        # For base stages (from a Docker image), use full build steps
        if ":" in stage.frm or "/" in stage.frm:
            # FROM a Docker image - full default build
            build_steps = [
                "install_system_packages",
                "install_pip_packages",
                "create_user",
            ]
        else:
            # FROM another stage - minimal default (just inherits)
            build_steps = []
    else:
        build_steps = stage.build_steps

    # Track what we find in build_steps
    has_create_user = False
    has_switch_user = False
    has_copy_cached_assets = False

    # Process build_steps into ordered sections
    ordered_steps = []
    for step in build_steps:
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
        else:
            # Custom RUN command
            ordered_steps.append({"type": "custom", "command": step})

    # Validation: Check if user is defined but create_user not in build_steps
    if stage.user and not has_create_user and not has_switch_user:
        print(
            f"⚠️  Warning: Stage '{stage_name}' defines user='{stage.user}' but has no 'create_user' or 'switch_user' in build_steps",
            file=sys.stderr,
        )
        print("   The user field will have no effect.", file=sys.stderr)

    # Validation: Check if switch_user used but no create_user in this or parent stages
    if has_switch_user:
        # Walk up the stage hierarchy to find if any parent has create_user
        user_created = has_create_user
        current_stage_name = stage_name
        visited = set()

        while not user_created and current_stage_name in stages_dict:
            if current_stage_name in visited:
                break
            visited.add(current_stage_name)

            current_stage = stages_dict[current_stage_name]
            if current_stage.build_steps and "create_user" in current_stage.build_steps:
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

    # Warn if cached_assets defined but copy_cached_assets not in build_steps
    if stage.cached_assets and not has_copy_cached_assets:
        print(
            f"⚠️  Warning: Stage '{stage_name}' has cached_assets but 'copy_cached_assets' not in build_steps",
            file=sys.stderr,
        )
        print(
            "   Assets will be downloaded but not copied into the image.",
            file=sys.stderr,
        )
        print(
            "   Add 'copy_cached_assets' to build_steps to use them.", file=sys.stderr
        )

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
    )

    template = env.get_template("Dockerfile.j2")

    # Build stages dict with defaults if needed
    stages = dict(config.stages)

    # Add default development stage if missing
    if "development" not in stages:
        from container_magic.core.config import StageConfig

        stages["development"] = StageConfig(frm="base")

    # Add default production stage if missing
    if "production" not in stages:
        from container_magic.core.config import StageConfig

        stages["production"] = StageConfig(frm="base")

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
        ordered_steps, has_copy_cached_assets, cached_assets_data = (
            process_stage_build_steps(
                stage_config, stage_name, output_path.parent, stages
            )
        )

        # Determine user for this stage (fallback to production.user or 'user')
        stage_user = stage_config.user or config.production.user or "user"

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
                "user": stage_user,
                "ordered_steps": ordered_steps,
            }
        )

    dockerfile_content = template.render(
        stages=stages_data,
        workspace_name=config.project.workspace,
        production_user=config.production.user,
        production_entrypoint=config.production.entrypoint,
    )

    with open(output_path, "w") as f:
        f.write(dockerfile_content)
