"""Tests for devcontainer.json generation."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from container_magic.core.config import ContainerMagicConfig
from container_magic.generators.devcontainer import generate_devcontainer


def _config(**extra):
    return {
        "names": {"image": "demo", "workspace": "workspace", "user": "app"},
        "stages": {
            "base": {"from": "python:3.11-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
        **extra,
    }


def _generate(config_dict):
    config = ContainerMagicConfig(**config_dict)
    with TemporaryDirectory() as tmp:
        project_dir = Path(tmp)
        generate_devcontainer(config, project_dir)
        path = project_dir / ".devcontainer" / "devcontainer.json"
        return json.loads(path.read_text()) if path.exists() else None


def test_not_generated_by_default():
    assert _generate(_config()) is None


def test_generated_when_enabled():
    dc = _generate(_config(devcontainer=True))
    assert dc is not None
    assert dc["name"] == "demo"
    assert dc["build"]["dockerfile"] == "../Dockerfile"
    assert dc["build"]["context"] == ".."
    assert dc["build"]["target"] == "development"
    assert dc["build"]["args"]["USER_NAME"] == "app"
    assert dc["build"]["args"]["WORKSPACE_NAME"] == "workspace"


def test_workspace_mount_and_folder():
    dc = _generate(_config(devcontainer=True))
    assert dc["workspaceFolder"] == "/home/app/workspace"
    assert (
        dc["workspaceMount"]
        == "source=${localWorkspaceFolder}/workspace,target=/home/app/workspace,type=bind"
    )


def test_remote_user_and_uid_update_for_non_root():
    dc = _generate(_config(devcontainer=True))
    assert dc["remoteUser"] == "app"
    assert dc["updateRemoteUserUID"] is True


def test_root_user_has_no_uid_update():
    config = {
        "names": {"image": "demo", "workspace": "ws", "user": "root"},
        "stages": {
            "base": {"from": "python:3.11-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
        "devcontainer": True,
    }
    dc = _generate(config)
    assert dc["remoteUser"] == "root"
    assert "updateRemoteUserUID" not in dc
    assert dc["workspaceFolder"] == "/root/ws"


def test_forward_ports_from_commands():
    dc = _generate(
        _config(
            devcontainer=True,
            commands={
                "serve": {
                    "command": "python -m http.server 8000",
                    "ports": ["8000:8000"],
                },
                "api": {
                    "command": "uvicorn app:app",
                    "ports": ["9000:9000", "9001:9001"],
                },
            },
        )
    )
    assert dc["forwardPorts"] == [8000, 9000, 9001]


def test_no_forward_ports_key_when_no_command_ports():
    dc = _generate(_config(devcontainer=True))
    assert "forwardPorts" not in dc
