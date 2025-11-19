"""Dockerfile generation from configuration."""

from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from container_magic.core.config import ContainerMagicConfig
from container_magic.core.templates import (
    detect_package_manager,
    detect_shell,
    detect_user_creation_style,
)


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

    # Auto-detect package manager and shell if not specified
    package_manager = config.template.package_manager or detect_package_manager(
        config.template.base
    )
    shell = config.template.shell or detect_shell(config.template.base)
    user_creation_style = detect_user_creation_style(config.template.base)

    # Default build order if not specified
    if config.template.build_steps is None:
        build_steps = [
            "install_system_packages",
            "install_pip_packages",
            "create_user",
        ]
    else:
        build_steps = config.template.build_steps

    # Process build_steps into ordered sections
    ordered_steps = []
    for step in build_steps:
        if step == "install_system_packages":
            ordered_steps.append({"type": "system_packages"})
        elif step == "install_pip_packages":
            ordered_steps.append({"type": "pip_packages"})
        elif step == "create_user":
            ordered_steps.append({"type": "user"})
        else:
            # Custom RUN command
            ordered_steps.append({"type": "custom", "command": step})

    dockerfile_content = template.render(
        base_image=config.template.base,
        apt_packages=config.template.packages.apt,
        pip_packages=config.template.packages.pip,
        env_vars=config.template.env,
        workspace_name=config.project.workspace,
        production_user=config.production.user,
        production_entrypoint=config.production.entrypoint,
        package_manager=package_manager,
        shell=shell,
        user_creation_style=user_creation_style,
        ordered_steps=ordered_steps,
    )

    with open(output_path, "w") as f:
        f.write(dockerfile_content)
