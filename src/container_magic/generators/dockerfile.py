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

    # Handle build_steps: can be a list (backward compat) or BuildStepsConfig object
    from container_magic.core.config import BuildStepsConfig

    if config.template.build_steps is None:
        build_steps = BuildStepsConfig()
    elif isinstance(config.template.build_steps, list):
        # Backward compatibility: treat list as after_packages
        build_steps = BuildStepsConfig(after_packages=config.template.build_steps)
    else:
        build_steps = config.template.build_steps

    dockerfile_content = template.render(
        base_image=config.template.base,
        apt_packages=config.template.packages.apt,
        pip_packages=config.template.packages.pip,
        build_steps_before_packages=build_steps.before_packages,
        build_steps_after_packages=build_steps.after_packages,
        build_steps_after_user=build_steps.after_user,
        workspace_name=config.project.workspace,
        production_user=config.production.user,
        production_entrypoint=config.production.entrypoint,
        package_manager=package_manager,
        shell=shell,
        user_creation_style=user_creation_style,
    )

    with open(output_path, "w") as f:
        f.write(dockerfile_content)
