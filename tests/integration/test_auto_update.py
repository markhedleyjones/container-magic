"""Integration tests for auto_update feature."""

import subprocess

import pytest


@pytest.fixture
def test_project(tmp_path):
    """Create a test project with auto_update enabled."""
    project_dir = tmp_path / "test-auto-update"
    project_dir.mkdir()

    # Initialize project
    result = subprocess.run(
        ["cm", "init", "--compact", "--here", "python"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    return project_dir


def test_auto_update_enabled_by_default(test_project):
    """Test that auto_update defaults to true and is omitted from scaffold."""
    # Verify auto_update is not present in scaffold (default is True, omitted as noise)
    config = (test_project / "cm.yaml").read_text()
    assert "auto_update" not in config

    # Check that Justfile has runtime auto_update detection
    justfile = (test_project / "Justfile").read_text()
    assert "grep -E" in justfile  # Runtime check for auto_update
    assert "auto_update_off=$(grep -E" in justfile  # Checking for opt-out pattern
    assert "Run 'cm update' to regenerate" in justfile  # Warning when disabled
    assert "cm update" in justfile  # Auto-update call in default branch


def test_auto_update_disabled_requires_manual_update(test_project):
    """Test that auto_update: false disables auto-regeneration."""
    # Disable auto_update explicitly
    config_path = test_project / "cm.yaml"
    config = config_path.read_text()
    config += "\n  auto_update: false\n" if "project:" in config else config
    # Insert auto_update under project section
    config = config.replace("project:\n", "project:\n  auto_update: false\n", 1)
    config_path.write_text(config)

    # Regenerate with new setting
    result = subprocess.run(
        ["cm", "update"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Check that Justfile still has both code paths (runtime detection)
    justfile = (test_project / "Justfile").read_text()
    assert "Run 'cm update' to regenerate" in justfile
    assert "cm update" in justfile


def test_auto_update_in_generated_justfile(tmp_path):
    """Test that Justfile uses runtime detection for auto_update."""
    # Create project
    project_dir = tmp_path / "test-auto-enabled"
    project_dir.mkdir()

    # Initialize with compact config
    result = subprocess.run(
        ["cm", "init", "--compact", "--here", "python"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Verify Justfile contains runtime auto_update detection
    justfile = (project_dir / "Justfile").read_text()

    # The Justfile should check for auto_update: false (opt-out) at runtime
    assert "auto_update_off=$(grep -E" in justfile, (
        "Justfile should check for auto_update: false at runtime using grep"
    )

    # Should have both code paths (if disabled, warn; else auto-update)
    assert "cm update" in justfile
    assert "Run 'cm update' to regenerate" in justfile
