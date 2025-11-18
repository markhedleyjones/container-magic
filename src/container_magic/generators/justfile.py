"""Justfile generation from configuration."""

import hashlib
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from container_magic.core.config import ContainerMagicConfig
from container_magic.core.runtime import get_runtime


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
        config_path: Path to container-magic.yaml (for hash calculation)
        output_path: Path to write Justfile
    """
    env = Environment(
        loader=PackageLoader("container_magic", "templates"),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    template = env.get_template("Justfile.j2")

    # Calculate config hash for drift detection
    config_hash = calculate_config_hash(config_path)

    # Determine runtime
    runtime = get_runtime(config.runtime.backend)

    # Build feature flags for run command
    features = {
        "display": "display" in config.development.features,
        "gpu": "gpu" in config.development.features,
        "audio": "audio" in config.development.features,
        "aws_credentials": "aws_credentials" in config.development.features,
    }

    justfile_content = template.render(
        config_hash=config_hash,
        project_name=config.project.name,
        workspace_name=config.project.workspace,
        runtime=runtime.value,
        privileged=config.runtime.privileged,
        mount_workspace=config.development.mount_workspace,
        shell=config.development.shell,
        features=features,
    )

    with open(output_path, "w") as f:
        f.write(justfile_content)
