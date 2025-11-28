"""Justfile generation from configuration."""

import hashlib
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from container_magic.core.config import ContainerMagicConfig
from container_magic.core.runtime import get_runtime
from container_magic.core.templates import detect_shell


def calculate_config_hash(config_path: Path) -> str:
    """Calculate SHA256 hash of configuration file."""
    with open(config_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def generate_justfile(
    config: ContainerMagicConfig, config_path: Path, output_path: Path
) -> None:
    """
    Generate Justfile from configuration.

    Args:
        config: Container-magic configuration
        config_path: Path to config file (for hash calculation)
        output_path: Path to write Justfile
    """
    env = Environment(
        loader=PackageLoader("container_magic", "templates"),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )

    template = env.get_template("Justfile.j2")

    # Calculate config hash for drift detection
    config_hash = calculate_config_hash(config_path)

    # Determine runtime
    runtime = get_runtime(config.runtime.backend)

    # Determine which stage to use for development
    # Prefer "development" stage if it exists, otherwise use "base"
    dev_stage = "development" if "development" in config.stages else "base"
    dev_stage_config = config.stages[dev_stage]

    # Auto-detect shell if not specified in stage
    shell = dev_stage_config.shell or detect_shell(dev_stage_config.frm)

    # Build feature flags for run command
    features = {
        "display": "display" in config.runtime.features,
        "gpu": "gpu" in config.runtime.features,
        "audio": "audio" in config.runtime.features,
        "aws_credentials": "aws_credentials" in config.runtime.features,
    }

    justfile_content = template.render(
        config_hash=config_hash,
        project_name=config.project.name,
        workspace_name=config.project.workspace,
        auto_update=config.project.auto_update,
        runtime=runtime.value,
        privileged=config.runtime.privileged,
        mount_workspace=True,  # Always mount workspace in development
        shell=shell,
        features=features,
        dev_stage=dev_stage,
    )

    # Generate custom commands if defined
    custom_commands_content = ""
    if config.commands:
        command_template = env.get_template("custom_command.j2")
        # Merge stage environment variables with command-specific ones
        stage_env = dev_stage_config.env or {}

        # Determine container home directory for volume mounts (must match Dockerfile)
        user_config = (
            config.project.production_user
            or config.project.development_user
            or config.project.user
        )
        container_home = (
            (user_config.home or f"/home/{user_config.name}")
            if user_config
            else "/root"
        )

        for command_name, command_spec in config.commands.items():
            # Escape dollar signs in command so they expand in the container
            command_escaped = command_spec.command.replace("$", r"\$")
            # Merge stage env with command env (command env takes precedence)
            merged_env = {**stage_env, **(command_spec.env or {})}
            custom_commands_content += "\n" + command_template.render(
                command_name=command_name,
                description=command_spec.description,
                command=command_escaped,
                args=command_spec.args,
                env=merged_env,
                allow_extra_args=command_spec.allow_extra_args,
                runtime=runtime.value,
                image_name=config.project.name,
                image_tag="development",
                shell=shell,
                workspace_name=config.project.workspace,
                container_home=container_home,
            )

    with open(output_path, "w") as f:
        f.write(justfile_content)
        if custom_commands_content:
            f.write("\n# Custom Commands\n")
            f.write(custom_commands_content)
