"""Dockerfile generation from configuration."""

from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from container_magic.core.config import ContainerMagicConfig


def generate_dockerfile(config: ContainerMagicConfig, output_path: Path) -> None:
    """
    Generate Dockerfile from configuration.

    Args:
        config: Container-magic configuration
        output_path: Path to write Dockerfile
    """
    env = Environment(
        loader=PackageLoader("container_magic", "templates"),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    template = env.get_template("Dockerfile.j2")

    dockerfile_content = template.render(
        base_image=config.template.base,
        apt_packages=config.template.packages.apt,
        pip_packages=config.template.packages.pip,
        workspace_name=config.project.workspace,
        production_user=config.production.user,
        production_entrypoint=config.production.entrypoint,
    )

    with open(output_path, "w") as f:
        f.write(dockerfile_content)
