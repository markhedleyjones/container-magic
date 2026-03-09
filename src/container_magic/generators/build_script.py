#!/usr/bin/env python3
"""Generate standalone build.sh script for production builds."""

from pathlib import Path

from jinja2 import Environment, PackageLoader

from container_magic.core.config import ContainerMagicConfig
from container_magic.core.steps import has_create_user_in_stages
from container_magic.core.symlinks import scan_workspace_symlinks


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

    # Get user info from config.names
    has_user = has_create_user_in_stages(config.stages)
    production_user_name = config.names.user or "root"
    production_user_uid = 1000 if has_user else 0
    production_user_gid = 1000 if has_user else 0
    production_user_home = f"/home/{production_user_name}" if has_user else "/root"

    # Scan workspace for external symlinks
    workspace_path = project_dir / config.names.workspace
    workspace_symlinks = scan_workspace_symlinks(workspace_path)

    content = template.render(
        project_name=config.names.image,
        workspace_name=config.names.workspace,
        default_target=default_target,
        production_user_name=production_user_name,
        production_user_uid=production_user_uid,
        production_user_gid=production_user_gid,
        production_user_home=production_user_home,
        backend=config.backend,
        workspace_symlinks=workspace_symlinks,
    )

    build_script = project_dir / "build.sh"
    build_script.write_text(content)
    build_script.chmod(0o755)
