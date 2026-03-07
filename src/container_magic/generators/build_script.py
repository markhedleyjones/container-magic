#!/usr/bin/env python3
"""Generate standalone build.sh script for production builds."""

from pathlib import Path

from jinja2 import Environment, PackageLoader

from container_magic.core.config import ContainerMagicConfig
from container_magic.core.steps import find_create_user_in_stages


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

    # Get user info from create_user steps
    user_info = find_create_user_in_stages(config.stages)
    production_user_name = user_info["username"] if user_info else "root"
    production_user_uid = (
        (user_info["uid"] if user_info["uid"] is not None else 1000) if user_info else 0
    )
    production_user_gid = (
        (user_info["gid"] if user_info["gid"] is not None else 1000) if user_info else 0
    )
    production_user_home = f"/home/{production_user_name}" if user_info else "/root"

    content = template.render(
        project_name=config.project.name,
        workspace_name=config.project.workspace,
        default_target=default_target,
        available_stages=available_stages,
        production_user_name=production_user_name,
        production_user_uid=production_user_uid,
        production_user_gid=production_user_gid,
        production_user_home=production_user_home,
    )

    build_script = project_dir / "build.sh"
    build_script.write_text(content)
    build_script.chmod(0o755)
