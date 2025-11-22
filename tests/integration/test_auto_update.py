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

    # Check that Justfile has the warning logic (not auto-update logic)
    justfile = (test_project / "Justfile").read_text()
    assert "Run 'cm update' to regenerate" in justfile

    # Should NOT have the auto-update call (only the warning message)
    # Check the section between hash mismatch and the end of that if block
    hash_check_section = justfile.split('if [ "$current" != "$expected" ]; then')[
        1
    ].split("# Build")[0]
    # Should have the warning
    assert "Run 'cm update' to regenerate" in hash_check_section
    # Should NOT have a standalone "cm update" command (only in echo statements)
    lines = hash_check_section.split("\n")
    for line in lines:
        stripped = line.strip()
        if stripped == "cm update" or (
            stripped.startswith("cm update") and "echo" not in line
        ):
            assert False, (
                "Found standalone 'cm update' command when auto_update is false"
            )


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
    """Test that auto_update setting is properly reflected in generated Justfile."""
    # Create project with auto_update enabled from the start
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

    # Enable auto_update in config
    config_path = project_dir / "cm.yaml"
    config = config_path.read_text()
    config = config.replace("auto_update: false", "auto_update: true")
    config_path.write_text(config)

    # Generate files with auto_update enabled
    result = subprocess.run(
        ["cm", "update"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Verify Justfile contains auto-update logic
    justfile = (project_dir / "Justfile").read_text()

    # Simple check: when auto_update is true, the justfile should have "cm update"
    # and should NOT have "Run 'cm update' to regenerate" warning
    assert "cm update" in justfile, (
        "Justfile should contain 'cm update' call when auto_update is true"
    )

    # The warning should not appear (it's in the else branch)
    # Check that the hash check section doesn't have the warning
    hash_check_section = justfile.split('if [ "$current" != "$expected" ]; then')[
        1
    ].split("# Build")[0]
    assert "Run 'cm update' to regenerate" not in hash_check_section, (
        "Justfile should not have manual update warning when auto_update is true"
    )
