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


def test_auto_update_disabled_requires_manual_update(test_project):
    """Test that auto_update: false requires manual update."""
    # Verify auto_update is false by default
    config = (test_project / "cm.yaml").read_text()
    assert "auto_update: false" in config

    # Check that Justfile has runtime auto_update detection
    justfile = (test_project / "Justfile").read_text()
    assert "grep -E" in justfile  # Runtime check for auto_update
    assert "auto_update: true" in justfile  # Checking for this pattern
    assert "Run 'cm update' to regenerate" in justfile  # Warning message in else branch
    assert "cm update" in justfile  # Auto-update call in if branch

    # The Justfile now always contains both code paths
    # Verify it has the runtime check
    assert "auto_update=$(grep -E" in justfile


def test_auto_update_enabled_regenerates_automatically(test_project):
    """Test that auto_update: true includes auto-regeneration in Justfile."""
    # Enable auto_update
    config_path = test_project / "cm.yaml"
    config = config_path.read_text()
    config = config.replace("auto_update: false", "auto_update: true")
    config_path.write_text(config)

    # Regenerate with new setting
    result = subprocess.run(
        ["cm", "update"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Check that Justfile now has auto-update logic
    justfile = (test_project / "Justfile").read_text()
    assert "Auto-update enabled" in justfile or "regenerating files" in justfile

    # Find the check-config section and verify cm update is called
    lines = justfile.split("\n")
    found_check = False
    found_cm_update = False
    in_hash_check = False

    for line in lines:
        if 'if [ "$current" != "$expected" ]; then' in line:
            in_hash_check = True
            found_check = True
        elif in_hash_check and "cm update" in line and not line.strip().startswith("#"):
            found_cm_update = True
            break
        elif (
            in_hash_check
            and line.strip() == "fi"
            and "$current" in justfile.split(line)[0].split("if")[-1]
        ):
            break

    assert found_check, "Could not find config hash check in Justfile"
    assert found_cm_update, "Justfile should call 'cm update' when auto_update is true"


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

    # The Justfile should always check auto_update at runtime using grep
    assert "auto_update=$(grep -E" in justfile, (
        "Justfile should check auto_update at runtime using grep"
    )

    # Should have both code paths (if auto_update enabled, else manual)
    assert "cm update" in justfile
    assert "Run 'cm update' to regenerate" in justfile
