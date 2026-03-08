"""Justfile generation from configuration."""

import hashlib
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from container_magic.core.config import ContainerMagicConfig
from container_magic.core.runtime import get_runtime
from container_magic.core.templates import detect_shell, resolve_base_image


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
    shell = dev_stage_config.shell or detect_shell(
        resolve_base_image(dev_stage_config.frm, config.stages)
    )

    # Build feature flags for run command
    features = {
        "display": "display" in config.runtime.features,
        "gpu": "gpu" in config.runtime.features,
        "audio": "audio" in config.runtime.features,
        "aws_credentials": "aws_credentials" in config.runtime.features,
    }

    # Development always uses host user
    use_host_user = True

    # Container home directory for volume mounts
    # Development uses host user, so home is resolved at runtime via $(echo ~)
    container_home = "$(echo ~)"

    justfile_content = template.render(
        config_hash=config_hash,
        project_name=config.names.project,
        workspace_name=config.names.workspace,
        auto_update=config.auto_update,
        runtime=runtime.value,
        privileged=config.runtime.privileged,
        network=config.runtime.network_mode,
        mount_workspace=True,  # Always mount workspace in development
        shell=shell,
        features=features,
        volumes=config.runtime.volumes,
        devices=config.runtime.devices,
        dev_stage=dev_stage,
        container_home=container_home,
        use_host_user=use_host_user,
        ipc=config.runtime.ipc if config.runtime else None,
    )

    # Generate custom commands if defined
    custom_commands_content = ""
    if config.commands:
        command_template = env.get_template("custom_command.j2")
        for command_name, command_spec in config.commands.items():
            # Escape dollar signs in command so they expand in the container
            command_escaped = command_spec.command.replace("$", r"\$")
            # Convert multi-line commands to single line with semicolons
            # This prevents breaking Justfile recipe indentation
            command_escaped = "; ".join(
                line for line in command_escaped.splitlines() if line.strip()
            )
            merged_env = command_spec.env or {}
            custom_commands_content += "\n" + command_template.render(
                command_name=command_name,
                description=command_spec.description,
                command=command_escaped,
                args=command_spec.args,
                env=merged_env,
                ports=command_spec.ports,
                runtime=runtime.value,
                network=config.runtime.network_mode,
                image_name=config.names.project,
                image_tag="development",
                shell=shell,
                workspace_name=config.names.workspace,
                container_home=container_home,
                features=features,
                volumes=config.runtime.volumes,
                devices=config.runtime.devices,
                ipc=command_spec.ipc
                or (config.runtime.ipc if config.runtime else None),
            )

    with open(output_path, "w") as f:
        f.write(justfile_content)
        if custom_commands_content:
            f.write("\n# Custom Commands\n")
            f.write(custom_commands_content)
