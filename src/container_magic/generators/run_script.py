#!/usr/bin/env python3
"""Generate standalone run.sh script for production containers."""

from pathlib import Path

from jinja2 import Environment, PackageLoader

from container_magic.core.config import ContainerMagicConfig
from container_magic.generators.dockerfile import get_user_config


def generate_run_script(config: ContainerMagicConfig, project_dir: Path) -> None:
    """Generate run.sh script from production containers.

    Args:
        config: Configuration object
        project_dir: Path to project directory
    """
    env = Environment(
        loader=PackageLoader("container_magic", "templates"),
        keep_trailing_newline=True,
    )
    template = env.get_template("run.sh.j2")

    # Determine runtime backend
    backend = config.runtime.backend if config.runtime else "auto"

    # Get production user and workspace info
    user_cfg = get_user_config(config)
    production_user = user_cfg.name if user_cfg else "root"
    workspace_name = config.project.workspace

    # Determine workdir based on production user
    if production_user == "root":
        workdir = "/root"
    else:
        workdir = f"/home/{production_user}"

    # Determine shell from production or base stage
    prod_stage = "production" if "production" in config.stages else "base"
    stage_config = config.stages[prod_stage]
    shell = stage_config.shell or "bash"

    # Escape dollar signs in command strings so they expand in the container
    commands_escaped = {}
    if config.commands:
        for cmd_name, cmd_spec in config.commands.items():
            cmd_copy = cmd_spec.copy(deep=True)
            cmd_copy.command = cmd_spec.command.replace("$", r"\$")
            commands_escaped[cmd_name] = cmd_copy

    content = template.render(
        project_name=config.project.name,
        workspace_name=workspace_name,
        workdir=workdir,
        shell=shell,
        backend=backend,
        privileged=config.runtime.privileged if config.runtime else False,
        network=config.runtime.network if config.runtime else None,
        commands=commands_escaped,
    )

    run_script = project_dir / "run.sh"
    run_script.write_text(content)
    run_script.chmod(0o755)
