"""Session-scoped fixtures that build base images for integration tests.

Two base images are built once per test session:

- cm-test:debian: Built from debian:bookworm-slim with Python installed via apt-get.
  The image name contains "debian" so container-magic's auto-detection (package manager,
  shell, user creation style) fires correctly. Tests the auto-detection path.

- cm-test:apk: Built from alpine:latest with Python installed via apk. The image name
  deliberately avoids "alpine" so auto-detection falls through to apt (incorrect),
  forcing the fixture to use explicit package_manager and shell overrides. This is the
  only way to verify those config fields actually work. Tests the override path.

This naming convention is deliberately inconsistent to cover both code paths.
"""

import shutil
import subprocess
from pathlib import Path

import pytest


def _has_container_runtime():
    return shutil.which("docker") or shutil.which("podman")


def _runtime():
    if shutil.which("docker"):
        return "docker"
    return "podman"


def _build_base_image(tmp_path_factory, config_yaml, image_tag, label):
    """Build a base image from a cm.yaml config string."""
    project = tmp_path_factory.mktemp(label)
    (project / "workspace").mkdir()
    (project / "cm.yaml").write_text(config_yaml)

    result = subprocess.run(
        ["cm", "update"],
        cwd=project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"cm update failed for {label}:\n{result.stderr}"

    # Extract tag from image_tag (e.g. "cm-test:debian" -> "debian")
    tag = image_tag.split(":")[1]
    result = subprocess.run(
        ["./build.sh", "--tag", tag],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, (
        f"build.sh failed for {label}:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return project


DEBIAN_CONFIG = """\
names:
  image: cm-test
  workspace: workspace
  user: root

stages:
  base:
    from: debian:bookworm-slim
    steps:
      - apt-get:
          install:
            - python3
            - python3-pip
            - python3-venv
            - bash

  development:
    from: base

  production:
    from: base
"""

ALPINE_CONFIG = """\
names:
  image: cm-test
  workspace: workspace
  user: root

runtime:
  shell: /bin/sh

stages:
  base:
    from: alpine:latest
    package_manager: apk
    steps:
      - apk:
          add:
            - python3
            - py3-pip

  development:
    from: base

  production:
    from: base
"""


@pytest.fixture(scope="session")
def debian_base_image(tmp_path_factory):
    """Build cm-test:debian from debian:bookworm-slim with Python installed."""
    if not _has_container_runtime():
        pytest.skip("No container runtime available")
    _build_base_image(tmp_path_factory, DEBIAN_CONFIG, "cm-test:debian", "debian-base")
    yield "cm-test:debian"
    subprocess.run(
        [_runtime(), "rmi", "-f", "cm-test:debian"],
        capture_output=True,
    )


@pytest.fixture(scope="session")
def alpine_base_image(tmp_path_factory):
    """Build cm-test:apk from alpine:latest with Python installed."""
    if not _has_container_runtime():
        pytest.skip("No container runtime available")
    _build_base_image(tmp_path_factory, ALPINE_CONFIG, "cm-test:apk", "alpine-base")
    yield "cm-test:apk"
    subprocess.run(
        [_runtime(), "rmi", "-f", "cm-test:apk"],
        capture_output=True,
    )
