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
    """Test that build.sh defaults to production target."""
    config = ContainerMagicConfig(
        project={"name": "test-project"},
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
    assert 'DEFAULT_TARGET="production"' in content


def test_build_script_custom_default_target(temp_project_dir):
    """Test that build.sh uses custom default target."""
    config = ContainerMagicConfig(
        project={"name": "test-project"},
        stages={
            "base": {"from": "python:3-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
            "testing": {"from": "base"},
        },
        build_script={"default_target": "testing"},
    )

    generate_build_script(config, temp_project_dir)
    build_script = temp_project_dir / "build.sh"

    assert build_script.exists()
    content = build_script.read_text()
    assert 'DEFAULT_TARGET="testing"' in content


def test_build_script_available_targets(temp_project_dir):
    """Test that build.sh includes all available targets."""
    config = ContainerMagicConfig(
        project={"name": "test-project"},
        stages={
            "base": {"from": "python:3-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
            "testing": {"from": "base"},
            "staging": {"from": "base"},
        },
    )

    generate_build_script(config, temp_project_dir)
    build_script = temp_project_dir / "build.sh"

    content = build_script.read_text()
    assert '"base"' in content
    assert '"development"' in content
    assert '"production"' in content
    assert '"testing"' in content
    assert '"staging"' in content


def test_build_script_executable(temp_project_dir):
    """Test that build.sh is executable."""
    config = ContainerMagicConfig(
        project={"name": "test-project"},
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
    """Test that build.sh --help shows all available targets."""
    config = ContainerMagicConfig(
        project={"name": "test-project"},
        stages={
            "base": {"from": "python:3-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
            "testing": {"from": "base"},
        },
        build_script={"default_target": "testing"},
    )

    generate_build_script(config, temp_project_dir)
    build_script = temp_project_dir / "build.sh"

    result = subprocess.run(
        [str(build_script), "--help"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Available targets:" in result.stdout
    assert "base" in result.stdout
    assert "development" in result.stdout
    assert "production" in result.stdout
    assert "testing (default)" in result.stdout


def test_build_script_invalid_target(temp_project_dir):
    """Test that build.sh rejects invalid targets."""
    config = ContainerMagicConfig(
        project={"name": "test-project"},
        stages={
            "base": {"from": "python:3-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
    )

    generate_build_script(config, temp_project_dir)
    build_script = temp_project_dir / "build.sh"

    result = subprocess.run(
        [str(build_script), "nonexistent"],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "Invalid target" in result.stderr


def test_build_script_accepts_all_stages(temp_project_dir):
    """Test that build.sh syntax is valid for all stage names."""
    config = ContainerMagicConfig(
        project={"name": "test-project"},
        stages={
            "base": {"from": "python:3-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
            "testing": {"from": "base"},
            "staging": {"from": "base"},
        },
    )

    generate_build_script(config, temp_project_dir)
    build_script = temp_project_dir / "build.sh"

    for stage in ["base", "development", "production", "testing", "staging"]:
        result = subprocess.run(
            ["bash", "-n", str(build_script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Syntax error in build.sh for stage {stage}"
