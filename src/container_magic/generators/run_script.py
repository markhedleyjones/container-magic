#!/usr/bin/env python3
"""Generate standalone run.sh script for production containers."""

from pathlib import Path

from jinja2 import Environment, PackageLoader

from container_magic.core.config import ContainerMagicConfig
from container_magic.core.runner import build_feature_flags
from container_magic.core.templates import (
    detect_shell,
    resolve_base_image,
    resolve_distro_shell,
)
from container_magic.core.volumes import expand_volumes_for_script, label_volumes


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
    backend = config.backend

    # Get user and workspace info from config.names
    has_user = config.names.user != "root"
    production_user = config.names.user or "root"
    workspace_name = config.names.workspace

    # Determine workdir based on production user
    if production_user == "root" or not has_user:
        workdir = "/root"
    else:
        workdir = f"/home/{production_user}"

    # Resolve effective runtime for production stage
    prod_stage = "production" if "production" in config.stages else "base"
    effective_rt = config.effective_runtime(prod_stage)

    # Determine interactive shell: runtime.shell > distro > image-name detection
    stage_config = config.stages[prod_stage]
    shell = (
        effective_rt.shell
        or resolve_distro_shell(prod_stage, config.stages)
        or detect_shell(resolve_base_image(stage_config.frm, config.stages))
    )

    # Escape dollar signs in command strings so they expand in the container
    commands_escaped = {}
    if config.commands:
        for cmd_name, cmd_spec in config.commands.items():
            cmd_copy = cmd_spec.model_copy(deep=True)
            cmd_copy.command = cmd_spec.command.replace("$", r"\$")
            commands_escaped[cmd_name] = cmd_copy

    features = build_feature_flags(effective_rt)

    # Expand volume variables and apply SELinux labels for production context
    expanded_volumes = expand_volumes_for_script(effective_rt.volumes, workdir)
    expanded_volumes = label_volumes(expanded_volumes)

    content = template.render(
        project_name=config.names.image,
        workspace_name=workspace_name,
        workdir=workdir,
        shell=shell,
        backend=backend,
        privileged=effective_rt.privileged,
        network=effective_rt.network_mode,
        features=features,
        volumes=expanded_volumes,
        devices=effective_rt.devices,
        commands=commands_escaped,
        ipc=effective_rt.ipc,
    )

    run_script = project_dir / "run.sh"
    run_script.write_text(content)
    run_script.chmod(0o755)
