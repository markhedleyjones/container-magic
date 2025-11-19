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
    stage: StageConfig, stage_name: str, project_dir: Path
) -> tuple[list[dict], bool, list[dict]]:
    """
    Process build steps for a stage.

    Returns:
        (ordered_steps, has_copy_cached_assets, cached_assets_data)
    """
    # Default build order if not specified
    if stage.build_steps is None:
        build_steps = [
            "install_system_packages",
            "install_pip_packages",
            "create_user",
        ]
    else:
        build_steps = stage.build_steps

    # Process build_steps into ordered sections
    ordered_steps = []
    has_copy_cached_assets = False
    for step in build_steps:
        if step == "install_system_packages":
            ordered_steps.append({"type": "system_packages"})
        elif step == "install_pip_packages":
            ordered_steps.append({"type": "pip_packages"})
        elif step == "create_user":
            ordered_steps.append({"type": "user"})
        elif step == "copy_cached_assets":
            ordered_steps.append({"type": "cached_assets"})
            has_copy_cached_assets = True
        else:
            # Custom RUN command
            ordered_steps.append({"type": "custom", "command": step})

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

    # Process all stages
    stages_data = []
    for stage_name, stage_config in config.stages.items():
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
            process_stage_build_steps(stage_config, stage_name, output_path.parent)
        )

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
