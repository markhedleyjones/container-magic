#!/usr/bin/env python3
"""Generate standalone build.sh script for production builds."""

from pathlib import Path

from jinja2 import Environment, PackageLoader

from container_magic.core.config import ContainerMagicConfig
from container_magic.generators.dockerfile import get_user_config


def generate_build_script(config: ContainerMagicConfig, project_dir: Path) -> None:
    """Generate build.sh script from configuration.

    Args:
        config: Configuration object
        project_dir: Path to project directory
    """
    env = Environment(
        loader=PackageLoader("container_magic", "templates"),
        keep_trailing_newline=True,
    )
    template = env.get_template("build.sh.j2")

    # Get default target from config (defaults to "production")
    default_target = config.build_script.default_target

    # Get all available stages for validation
    available_stages = list(config.stages.keys())

    content = template.render(
        project_name=config.project.name,
        workspace_name=config.project.workspace,
        default_target=default_target,
        available_stages=available_stages,
        production_user=get_user_config(config).name,
    )

    build_script = project_dir / "build.sh"
    build_script.write_text(content)
    build_script.chmod(0o755)
