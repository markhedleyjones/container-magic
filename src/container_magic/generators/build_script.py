#!/usr/bin/env python3
"""Generate standalone build.sh script for production builds."""

from pathlib import Path

from jinja2 import Environment, PackageLoader

from container_magic.core.config import ContainerMagicConfig


def generate_build_script(config: ContainerMagicConfig, project_dir: Path) -> None:
    """Generate build.sh script from configuration.

    Args:
        config: Configuration object
        project_dir: Path to project directory
    """
    env = Environment(loader=PackageLoader("container_magic", "templates"))
    template = env.get_template("build.sh.j2")

    # Use production stage if it exists, otherwise base
    prod_stage = "production" if "production" in config.stages else "base"

    content = template.render(
        project_name=config.project.name,
        workspace_name=config.project.workspace,
        production_stage=prod_stage,
        production_user=config.production.user if config.production else "user",
    )

    build_script = project_dir / "build.sh"
    build_script.write_text(content)
    build_script.chmod(0o755)
