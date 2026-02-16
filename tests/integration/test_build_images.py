"""Integration tests that actually build Docker images against representative base images.

Catches structural bugs (like incorrect adduser syntax on Alpine) that only
surface at build time. Marked @pytest.mark.slow so they can be excluded with:
    pytest -m "not slow"
"""

import shutil
import subprocess
from pathlib import Path

import pytest

# Each tuple: (base_image, package_manager, expected_shell)
BASE_IMAGES = [
    ("alpine:latest", "apk", "/bin/sh"),
    ("debian:bookworm-slim", "apt", "/bin/bash"),
    ("fedora:latest", "dnf", "/bin/bash"),
]


def _has_container_runtime():
    """Check if a container runtime (docker or podman) is available."""
    return shutil.which("docker") or shutil.which("podman")


def _runtime():
    """Return the available container runtime name."""
    if shutil.which("podman"):
        return "podman"
    return "docker"


def _image_name(base_image):
    """Derive a test image name from the base image."""
    return "cm-build-test-" + base_image.replace(":", "-").replace("/", "-")


pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not _has_container_runtime(),
        reason="No container runtime (docker/podman) available",
    ),
]


def _write_config(project_dir: Path, base_image: str):
    """Write a cm.yaml that exercises user creation and shell detection."""
    config = f"""\
project:
  name: {_image_name(base_image)}
  workspace: workspace

user:
  production:
    name: testuser
    uid: 1500
    gid: 1500

runtime:
  backend: auto

stages:
  base:
    from: {base_image}
    packages:
      pip: []

  development:
    from: base
    steps:
    - become_user

  production:
    from: base
    steps:
    - become_user
    - copy_workspace
"""
    (project_dir / "cm.yaml").write_text(config)


def _setup_and_build(tmp_path_factory, base_image):
    """Generate config, run cm update, build the production image."""
    project = tmp_path_factory.mktemp(base_image.replace(":", "-").replace("/", "-"))
    (project / "workspace").mkdir()
    _write_config(project, base_image)

    result = subprocess.run(
        ["cm", "update"],
        cwd=project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"cm update failed for {base_image}:\n{result.stderr}"
    )

    result = subprocess.run(
        ["./build.sh"],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, (
        f"Build failed for {base_image}:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return project


@pytest.fixture(scope="module")
def alpine_project(tmp_path_factory):
    """Build Alpine image once for the module."""
    project = _setup_and_build(tmp_path_factory, "alpine:latest")
    yield project
    subprocess.run(
        [_runtime(), "rmi", "-f", f"{_image_name('alpine:latest')}:latest"],
        capture_output=True,
    )


@pytest.fixture(scope="module")
def debian_project(tmp_path_factory):
    """Build Debian image once for the module."""
    project = _setup_and_build(tmp_path_factory, "debian:bookworm-slim")
    yield project
    subprocess.run(
        [_runtime(), "rmi", "-f", f"{_image_name('debian:bookworm-slim')}:latest"],
        capture_output=True,
    )


@pytest.fixture(scope="module")
def fedora_project(tmp_path_factory):
    """Build Fedora image once for the module."""
    project = _setup_and_build(tmp_path_factory, "fedora:latest")
    yield project
    subprocess.run(
        [_runtime(), "rmi", "-f", f"{_image_name('fedora:latest')}:latest"],
        capture_output=True,
    )


# Map base image to fixture name for parametrisation
IMAGE_FIXTURES = {
    "alpine:latest": "alpine_project",
    "debian:bookworm-slim": "debian_project",
    "fedora:latest": "fedora_project",
}


@pytest.fixture
def built_project(request):
    """Resolve the correct project fixture based on the base_image parameter."""
    base_image = request.param
    return request.getfixturevalue(IMAGE_FIXTURES[base_image])


def _run_in_container(project_dir: Path, command: str, timeout: int = 30):
    """Run a command inside the built container via run.sh."""
    return subprocess.run(
        ["./run.sh", command],
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@pytest.mark.parametrize(
    "built_project", [img for img, _, _ in BASE_IMAGES], indirect=True
)
def test_image_builds(built_project):
    """Verify that build.sh succeeds for each base image.

    The actual build happens in the fixture — if we get here, it passed.
    """
    assert built_project.exists()


@pytest.mark.parametrize(
    "built_project,base_image",
    [(img, img) for img, _, _ in BASE_IMAGES],
    indirect=["built_project"],
)
def test_user_created_correctly(built_project, base_image):
    """Verify that the production user exists with correct uid/gid."""
    result = _run_in_container(built_project, "id testuser")
    assert result.returncode == 0, (
        f"id testuser failed for {base_image}:\n{result.stdout}\n{result.stderr}"
    )
    assert "uid=1500" in result.stdout, (
        f"Expected uid=1500 for {base_image}, got: {result.stdout}"
    )
    assert "gid=1500" in result.stdout, (
        f"Expected gid=1500 for {base_image}, got: {result.stdout}"
    )


@pytest.mark.parametrize(
    "built_project,expected_shell",
    [(img, shell) for img, _, shell in BASE_IMAGES],
    indirect=["built_project"],
)
def test_shell_exists(built_project, expected_shell):
    """Verify the detected shell works inside the container."""
    result = _run_in_container(built_project, f"{expected_shell} -c 'echo shell_ok'")
    assert result.returncode == 0, (
        f"Shell {expected_shell} failed:\n{result.stdout}\n{result.stderr}"
    )
    assert "shell_ok" in result.stdout, f"Shell output missing: {result.stdout}"
