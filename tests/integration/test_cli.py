"""Integration tests for CLI commands."""

import subprocess

import pytest


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary directory for CLI tests."""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    return project_dir


def test_init_with_here_flag(temp_project_dir):
    """Test that --here flag creates project in current directory."""
    result = subprocess.run(
        ["cm", "init", "--here", "python"],
        cwd=temp_project_dir,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"cm init --here failed: {result.stderr}"

    # Check files were created in the directory (not in a subdirectory)
    assert (temp_project_dir / "container-magic.yaml").exists()
    assert (temp_project_dir / "Dockerfile").exists()
    assert (temp_project_dir / "Justfile").exists()
    assert (temp_project_dir / "workspace").exists()


def test_init_with_compact_flag(temp_project_dir):
    """Test that --compact flag creates cm.yaml instead of container-magic.yaml."""
    result = subprocess.run(
        ["cm", "init", "--compact", "--here", "python"],
        cwd=temp_project_dir,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"cm init --compact failed: {result.stderr}"

    # Check compact config file was created
    assert (temp_project_dir / "cm.yaml").exists()
    assert not (temp_project_dir / "container-magic.yaml").exists()

    # Check that compact file has no comments
    config_content = (temp_project_dir / "cm.yaml").read_text()
    comment_lines = [
        line for line in config_content.split("\n") if line.strip().startswith("#")
    ]
    assert len(comment_lines) == 0, "Compact config should not have comments"


def test_init_without_compact_has_comments(temp_project_dir):
    """Test that default (non-compact) config has comments."""
    result = subprocess.run(
        ["cm", "init", "--here", "python"],
        cwd=temp_project_dir,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    # Check full config file was created
    assert (temp_project_dir / "container-magic.yaml").exists()
    assert not (temp_project_dir / "cm.yaml").exists()

    # Check that full file has comments
    config_content = (temp_project_dir / "container-magic.yaml").read_text()
    assert "# Project configuration" in config_content
    assert "# Container runtime configuration" in config_content


def test_init_with_name_creates_subdirectory(tmp_path):
    """Test that providing a name creates a subdirectory."""
    result = subprocess.run(
        ["cm", "init", "python", "myproject"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    # Check files were created in subdirectory
    project_dir = tmp_path / "myproject"
    assert project_dir.exists()
    assert (project_dir / "container-magic.yaml").exists()
    assert (project_dir / "Dockerfile").exists()


def test_init_complex_template_name(temp_project_dir):
    """Test that complex template names like pytorch/pytorch:version work."""
    result = subprocess.run(
        [
            "cm",
            "init",
            "--here",
            "--compact",
            "pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime",
        ],
        cwd=temp_project_dir,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"Complex template failed: {result.stderr}"

    # Check files were created
    assert (temp_project_dir / "cm.yaml").exists()

    # Check that the FROM line in Dockerfile uses the full template name
    dockerfile_content = (temp_project_dir / "Dockerfile").read_text()
    assert "pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime" in dockerfile_content

    # Check that cm.yaml has the correct base image
    config_content = (temp_project_dir / "cm.yaml").read_text()
    assert "from: pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime" in config_content


def test_init_without_here_requires_name(tmp_path):
    """Test that cm init without --here requires a name argument."""
    result = subprocess.run(
        ["cm", "init", "python"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    # Should fail because name is required when not using --here
    assert result.returncode != 0
    assert (
        "name argument is required" in result.stderr.lower()
        or "required" in result.stderr.lower()
    )
