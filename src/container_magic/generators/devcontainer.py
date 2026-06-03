#!/usr/bin/env python3
"""Generate .devcontainer/devcontainer.json for IDE / Codespaces interop.

Maps the relevant parts of cm.yaml onto the Dev Container specification so the
same image cm builds can be opened in VS Code, GitHub Codespaces, or any
devcontainer-aware tool. Only written when `devcontainer: true` is set.
"""

import json
from pathlib import Path

from container_magic.core.config import ContainerMagicConfig


def _forward_ports(config: ContainerMagicConfig) -> list:
    """Collect host ports from custom-command `ports` declarations, in order."""
    ports: list = []
    for command in config.commands.values():
        for spec in command.ports:
            host = str(spec).split(":")[0].strip()
            if host.isdigit():
                port = int(host)
                if port not in ports:
                    ports.append(port)
    return ports


def generate_devcontainer(config: ContainerMagicConfig, project_dir: Path) -> None:
    """Write .devcontainer/devcontainer.json when enabled in the config."""
    if not config.devcontainer:
        return

    user = config.names.user
    has_user = user != "root"
    home = f"/home/{user}" if has_user else "/root"
    workspace = config.names.workspace
    container_workspace = f"{home}/{workspace}"

    devcontainer = {
        "name": config.names.image,
        "build": {
            "dockerfile": "../Dockerfile",
            "context": "..",
            "target": "development",
            "args": {
                "USER_NAME": user,
                "WORKSPACE_NAME": workspace,
                "USER_HOME": home,
            },
        },
        # Bind only the workspace directory, mirroring cm's development mount.
        "workspaceFolder": container_workspace,
        "workspaceMount": (
            f"source=${{localWorkspaceFolder}}/{workspace},"
            f"target={container_workspace},type=bind"
        ),
        "remoteUser": user,
    }

    # updateRemoteUserUID remaps the container user's UID/GID to the host
    # user's at runtime - the host-identity matching cm does for `cm run`.
    if has_user:
        devcontainer["updateRemoteUserUID"] = True

    ports = _forward_ports(config)
    if ports:
        devcontainer["forwardPorts"] = ports

    out_dir = project_dir / ".devcontainer"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "devcontainer.json").write_text(
        json.dumps(devcontainer, indent=2) + "\n"
    )
