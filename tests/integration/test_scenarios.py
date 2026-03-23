"""End-to-end scenario tests that build real containers and run workspace scripts.

These tests use two locally-built base images (see conftest.py):
- cm-test:debian: auto-detection works (name contains "debian")
- cm-test:apk: requires explicit distro or package_manager override (name avoids "alpine")

This naming convention is deliberately inconsistent to test both the auto-detection
and explicit override code paths. See conftest.py for details.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not shutil.which("docker") and not shutil.which("podman"),
        reason="No container runtime available",
    ),
]

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
CONFIGS_DIR = FIXTURES_DIR / "configs"
SCRIPTS_DIR = FIXTURES_DIR / "workspace_scripts"


def _runtime():
    if shutil.which("docker"):
        return "docker"
    return "podman"


def _setup_project(tmp_path, config_name, workspace_scripts=None):
    """Set up a project directory with config and workspace scripts."""
    project = tmp_path / "project"
    project.mkdir()
    workspace = project / "workspace"
    workspace.mkdir()

    shutil.copy(CONFIGS_DIR / config_name, project / "cm.yaml")

    if workspace_scripts:
        for script_name in workspace_scripts:
            shutil.copy(SCRIPTS_DIR / script_name, workspace / script_name)

    return project


def _build_and_run(project, command=None, timeout=300):
    """Run cm update, build.sh, and optionally run a command via run.sh."""
    result = subprocess.run(
        ["cm", "update"],
        cwd=project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"cm update failed:\n{result.stderr}"

    result = subprocess.run(
        ["./build.sh"],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    assert result.returncode == 0, (
        f"build.sh failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    if command is None:
        return None

    result = subprocess.run(
        ["./run.sh"] + command,
        cwd=project,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result


def test_python_app(debian_base_image, tmp_path):
    """Basic Python app: pip install, workspace script imports package."""
    project = _setup_project(
        tmp_path, "scenario_python_app.yaml", ["check_import.py"]
    )
    result = _build_and_run(project, ["python3", "workspace/check_import.py"])
    assert result.returncode == 0, f"Script failed:\n{result.stderr}"
    assert "import_ok" in result.stdout


def test_multistage(debian_base_image, tmp_path):
    """Multi-stage: builder is intermediate, production is leaf with root-owned workspace."""
    project = _setup_project(
        tmp_path, "scenario_multistage.yaml", ["check_import.py"]
    )
    result = _build_and_run(project, ["python3", "workspace/check_import.py"])
    assert result.returncode == 0, f"Script failed:\n{result.stderr}"
    assert "import_ok" in result.stdout

    # Verify workspace is root-owned (production copies without --chown)
    result = subprocess.run(
        [
            "./run.sh",
            "bash",
            "-c",
            "stat -c '%U:%G' ${WORKSPACE}/check_import.py",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "root:root" in result.stdout, (
        f"Expected root:root ownership, got: {result.stdout}"
    )


def test_alpine(alpine_base_image, tmp_path):
    """Alpine with explicit overrides: pip install, workspace script runs."""
    project = _setup_project(
        tmp_path, "scenario_alpine.yaml", ["check_import.py"]
    )
    result = _build_and_run(project, ["python3", "workspace/check_import.py"])
    assert result.returncode == 0, f"Script failed:\n{result.stderr}"
    assert "import_ok" in result.stdout


def test_custom_commands(debian_base_image, tmp_path):
    """Custom commands: env var is passed through and script reads it."""
    project = _setup_project(
        tmp_path, "scenario_commands.yaml", ["check_env.py"]
    )
    _build_and_run(project)  # build only

    result = subprocess.run(
        ["./run.sh", "check"],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Command failed:\n{result.stderr}"
    assert "APP_ENV=production" in result.stdout
    assert "env_ok" in result.stdout


def test_root_user(debian_base_image, tmp_path):
    """Root user: no USER directives, script runs as root."""
    project = _setup_project(
        tmp_path, "scenario_root_user.yaml", ["check_user.py"]
    )
    result = _build_and_run(project, ["python3", "workspace/check_user.py"])
    assert result.returncode == 0, f"Script failed:\n{result.stderr}"
    assert "uid=0" in result.stdout
    assert "user=root" in result.stdout

    # Verify no USER directives in generated Dockerfile
    dockerfile = (project / "Dockerfile").read_text()
    assert "USER " not in dockerfile
