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
        ["cm", "init", "--here", "python"],
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

    # Check that Justfile always runs cm update before building
    justfile = (test_project / "Justfile").read_text()
    assert "cm update" in justfile  # Always regenerate before build


def test_auto_update_disabled_still_regenerates_on_build(test_project):
    """Test that build always runs cm update regardless of auto_update setting."""
    # Disable auto_update explicitly
    config_path = test_project / "cm.yaml"
    config = config_path.read_text()
    # Insert auto_update at root level (after names block)
    config = config.replace("stages:\n", "auto_update: false\n\nstages:\n", 1)
    config_path.write_text(config)

    # Regenerate with new setting
    result = subprocess.run(
        ["cm", "update"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Check that Justfile still always runs cm update before build
    justfile = (test_project / "Justfile").read_text()
    assert "cm update" in justfile
