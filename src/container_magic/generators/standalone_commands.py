"""Standalone command script generation from configuration."""

from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from container_magic.core.config import ContainerMagicConfig
from container_magic.core.templates import detect_shell


def generate_standalone_command_scripts(
    config: ContainerMagicConfig, output_dir: Path
) -> list[Path]:
    """
    Generate standalone scripts for commands with standalone=True.

    Cleans up any orphaned standalone scripts (from commands that no longer
    have standalone=True or no longer exist).

    Args:
        config: Container-magic configuration
        output_dir: Directory to write scripts

    Returns:
        List of paths to generated scripts
    """
    # Find all existing standalone scripts
    existing_scripts = set(output_dir.glob("*.sh"))
    # Exclude build.sh and run.sh which are not command scripts
    existing_scripts.discard(output_dir / "build.sh")
    existing_scripts.discard(output_dir / "run.sh")

    if not config.commands:
        # Clean up all standalone scripts if no commands defined
        for script in existing_scripts:
            script.unlink()
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

    # Determine workdir (same as in run_script.py)
    workdir = (
        f"/home/{config.project.production_user.name}"
        if config.project.production_user
        else "/root"
    )

    generated_scripts = []

    for command_name, command_spec in config.commands.items():
        script_path = output_dir / f"{command_name}.sh"

        if command_spec.standalone:
            # Generate standalone script
            content = template.render(
                command_name=command_name,
                description=command_spec.description,
                project_name=config.project.name,
                workdir=workdir,
                shell=shell,
                backend=backend,
                privileged=config.runtime.privileged if config.runtime else False,
                env=command_spec.env,
                command=command_spec.command,
            )

            script_path.write_text(content)
            script_path.chmod(0o755)
            generated_scripts.append(script_path)
        elif script_path in existing_scripts:
            # Command exists but standalone=false, delete orphaned script
            script_path.unlink()

    # Clean up completely orphaned scripts (commands that no longer exist)
    current_command_scripts = {
        output_dir / f"{name}.sh" for name in config.commands.keys()
    }
    orphaned_scripts = existing_scripts - current_command_scripts
    for script in orphaned_scripts:
        script.unlink()

    return generated_scripts
