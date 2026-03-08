"""Integration tests for build.sh script generation and execution."""

import subprocess
import tempfile
from pathlib import Path

import pytest

from container_magic.core.config import ContainerMagicConfig
from container_magic.generators.build_script import generate_build_script


@pytest.fixture
def temp_project_dir():
    """Create temporary directory for test project."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_build_script_default_target_production(temp_project_dir):
    """Test that build.sh uses production target."""
    config = ContainerMagicConfig(
        names={"image": "test-project", "user": "root"},
        stages={
            "base": {"from": "python:3-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
    )

    generate_build_script(config, temp_project_dir)
    build_script = temp_project_dir / "build.sh"

    assert build_script.exists()
    content = build_script.read_text()
    assert 'TARGET="production"' in content
    assert 'TAG="latest"' in content


def test_build_script_executable(temp_project_dir):
    """Test that build.sh is executable."""
    config = ContainerMagicConfig(
        names={"image": "test-project", "user": "root"},
        stages={
            "base": {"from": "python:3-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
    )

    generate_build_script(config, temp_project_dir)
    build_script = temp_project_dir / "build.sh"

    assert build_script.exists()
    assert build_script.stat().st_mode & 0o111


def test_build_script_help_output(temp_project_dir):
    """Test that build.sh --help shows usage information."""
    config = ContainerMagicConfig(
        names={"image": "test-project", "user": "root"},
        stages={
            "base": {"from": "python:3-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
    )

    generate_build_script(config, temp_project_dir)
    build_script = temp_project_dir / "build.sh"

    result = subprocess.run(
        [str(build_script), "--help"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Usage:" in result.stdout
    assert "--tag" in result.stdout
    assert "--uid" in result.stdout
    assert "--gid" in result.stdout


def test_build_script_tag_override(temp_project_dir):
    """Test that build.sh --tag overrides the default tag."""
    config = ContainerMagicConfig(
        names={"image": "test-project", "user": "root"},
        stages={
            "base": {"from": "python:3-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
    )

    generate_build_script(config, temp_project_dir)
    build_script = temp_project_dir / "build.sh"

    content = build_script.read_text()
    assert 'TAG="latest"' in content
    assert "--tag" in content


def test_build_script_rejects_unknown_args(temp_project_dir):
    """Test that build.sh rejects unknown positional arguments."""
    config = ContainerMagicConfig(
        names={"image": "test-project", "user": "root"},
        stages={
            "base": {"from": "python:3-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
    )

    generate_build_script(config, temp_project_dir)
    build_script = temp_project_dir / "build.sh"

    result = subprocess.run(
        [str(build_script), "production"],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "Unknown argument" in result.stderr
