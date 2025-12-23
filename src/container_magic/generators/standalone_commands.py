"""Standalone command script generation from configuration."""

from pathlib import Path
from typing import List

from jinja2 import Environment, PackageLoader, select_autoescape

from container_magic.core.config import ContainerMagicConfig
from container_magic.core.templates import detect_shell
from container_magic.generators.dockerfile import get_user_config


def generate_standalone_command_scripts(
    config: ContainerMagicConfig, output_dir: Path
) -> List[Path]:
    """
    Generate standalone scripts for commands with standalone=True.

    Does not automatically delete old scripts - users are responsible
    for cleaning up scripts when commands are removed or renamed.

    Args:
        config: Container-magic configuration
        output_dir: Directory to write scripts

    Returns:
        List of paths to generated scripts
    """
    if not config.commands:
        return []

    env = Environment(
        loader=PackageLoader("container_magic", "templates"),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )

    template = env.get_template("standalone_command.sh.j2")

    # Get base stage for shell detection
    base_stage = config.stages.get("base")
    if not base_stage:
        raise ValueError("No base stage defined in configuration")

    shell = base_stage.shell or detect_shell(base_stage.frm)

    # Determine backend
    backend = config.runtime.backend if config.runtime else "auto"

    # Determine workdir from production user config
    user_cfg = get_user_config(config, target="production")
    if user_cfg and user_cfg.name:
        workdir = user_cfg.home or f"/home/{user_cfg.name}"
    else:
        workdir = "/root"

    generated_scripts = []

    for command_name, command_spec in config.commands.items():
        if command_spec.standalone:
            script_path = output_dir / f"{command_name}.sh"

            # Escape dollar signs in command so they expand in the container
            command_escaped = command_spec.command.replace("$", r"\$")

            # Generate standalone script
            content = template.render(
                command_name=command_name,
                description=command_spec.description,
                project_name=config.project.name,
                workdir=workdir,
                shell=shell,
                backend=backend,
                privileged=config.runtime.privileged if config.runtime else False,
                network=config.runtime.network if config.runtime else None,
                env=command_spec.env,
                command=command_escaped,
                workspace_name=config.project.workspace,
            )

            script_path.write_text(content)
            script_path.chmod(0o755)
            generated_scripts.append(script_path)

    return generated_scripts
