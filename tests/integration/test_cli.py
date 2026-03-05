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
    assert (temp_project_dir / "cm.yaml").exists()
    assert (temp_project_dir / "Dockerfile").exists()
    assert (temp_project_dir / "Justfile").exists()
    assert (temp_project_dir / "workspace").exists()


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
    assert (project_dir / "cm.yaml").exists()
    assert (project_dir / "Dockerfile").exists()


def test_init_complex_template_name(temp_project_dir):
    """Test that complex template names like pytorch/pytorch:version work."""
    result = subprocess.run(
        [
            "cm",
            "init",
            "--here",
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


def test_gitignore_created_for_new_project(temp_project_dir):
    """Test that .gitignore is created for new projects."""
    result = subprocess.run(
        ["cm", "init", "--here", "python"],
        cwd=temp_project_dir,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    # Check .gitignore exists and has required entries
    gitignore = temp_project_dir / ".gitignore"
    assert gitignore.exists()

    content = gitignore.read_text()
    assert ".cm-cache/" in content
    assert "Justfile" in content


def test_gitignore_appends_to_existing(temp_project_dir):
    """Test that existing .gitignore is preserved and container-magic entries are added."""
    # Create existing .gitignore with some content
    existing_gitignore = temp_project_dir / ".gitignore"
    existing_content = """# My existing ignores
*.pyc
__pycache__/
.env
"""
    existing_gitignore.write_text(existing_content)

    # Initialize project
    result = subprocess.run(
        ["cm", "init", "--here", "python"],
        cwd=temp_project_dir,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    # Check .gitignore preserved existing content and added container-magic entries
    content = existing_gitignore.read_text()

    # Original content should still be there
    assert "# My existing ignores" in content
    assert "*.pyc" in content
    assert "__pycache__/" in content
    assert ".env" in content

    # Container-magic entries should be added
    assert ".cm-cache/" in content
    assert "Justfile" in content


def test_gitignore_does_not_duplicate_entries(temp_project_dir):
    """Test that running init twice doesn't duplicate .gitignore entries."""
    # Create existing .gitignore with container-magic entries already present
    existing_gitignore = temp_project_dir / ".gitignore"
    existing_content = """# My project
*.log

.cm-cache/
Justfile
"""
    existing_gitignore.write_text(existing_content)

    # Initialize project
    result = subprocess.run(
        ["cm", "init", "--here", "python"],
        cwd=temp_project_dir,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    # Check .gitignore doesn't have duplicates
    content = existing_gitignore.read_text()
    lines = content.split("\n")

    # Count occurrences of each line
    assert lines.count(".cm-cache/") == 1, "Should not duplicate .cm-cache/"
    assert lines.count("Justfile") == 1, "Should not duplicate Justfile"
