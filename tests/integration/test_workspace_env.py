"""Test that $WORKSPACE environment variable points to actual mounted workspace."""

import subprocess
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def test_project():
    """Create a temporary test project."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        # Initialize a basic Python project via cm command
        init_result = subprocess.run(
            ["cm", "init", "python", "test-workspace-env"],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        assert init_result.returncode == 0, f"cm init failed: {init_result.stderr}"

        # The init creates a subdirectory with the project name
        actual_project_dir = project_dir / "test-workspace-env"

        # Create a simple workspace file to verify mount
        workspace_dir = actual_project_dir / "workspace"
        workspace_dir.mkdir(exist_ok=True)
        test_file = workspace_dir / "test.txt"
        test_file.write_text("workspace test file\n")

        yield actual_project_dir


def test_workspace_env_points_to_mounted_path(test_project):
    """Test that $WORKSPACE env var points to the actual mounted workspace."""
    # Build the image
    build_result = subprocess.run(
        ["just", "build"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert build_result.returncode == 0, f"Build failed: {build_result.stderr}"

    # Test 1: Verify $WORKSPACE variable exists and is set
    result = subprocess.run(
        ["just", "run", "echo $WORKSPACE"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Command failed: {result.stderr}"
    workspace_path = result.stdout.strip()
    assert workspace_path, "WORKSPACE variable is empty or not set"

    # Test 2: Verify $WORKSPACE points to a valid directory inside container
    result = subprocess.run(
        ["just", "run", "test -d $WORKSPACE && echo 'OK'"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"$WORKSPACE directory does not exist: {result.stderr}"
    )
    assert "OK" in result.stdout, f"$WORKSPACE is not a directory: {result.stdout}"

    # Test 3: Verify workspace file is accessible via $WORKSPACE
    result = subprocess.run(
        ["just", "run", "cat $WORKSPACE/test.txt"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Failed to access file via $WORKSPACE: {result.stderr}"
    )
    assert "workspace test file" in result.stdout, (
        f"Wrong file content: {result.stdout}"
    )

    # Test 4: Verify $WORKSPACE path is consistent (same in multiple invocations)
    result1 = subprocess.run(
        ["just", "run", "echo $WORKSPACE"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    result2 = subprocess.run(
        ["just", "run", "echo $WORKSPACE"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert result1.stdout.strip() == result2.stdout.strip(), (
        f"$WORKSPACE path changed: {result1.stdout.strip()} vs {result2.stdout.strip()}"
    )

    # Test 5: Verify $WORKSPACE is accessible in custom commands
    result = subprocess.run(
        ["just", "run", "ls $WORKSPACE/"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Failed to list $WORKSPACE: {result.stderr}"
    assert "test.txt" in result.stdout, (
        f"test.txt not found in $WORKSPACE listing: {result.stdout}"
    )


def test_workspace_env_with_custom_command(test_project):
    """Test that $WORKSPACE works in custom commands."""
    # Add a custom command that uses $WORKSPACE
    config_path = test_project / "cm.yaml"
    config_content = config_path.read_text()

    # Add a custom command section
    custom_command = """
commands:
  verify-workspace:
    command: test -f $WORKSPACE/test.txt && echo "Workspace verified"
    description: Verify workspace is mounted correctly
"""
    config_content += "\n" + custom_command
    config_path.write_text(config_content)

    # Regenerate files
    regen_result = subprocess.run(
        ["cm", "update"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert regen_result.returncode == 0, f"Update failed: {regen_result.stderr}"

    # Run the custom command
    result = subprocess.run(
        ["./run.sh", "verify-workspace"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Custom command failed: {result.stderr}"
    assert "Workspace verified" in result.stdout, f"Unexpected output: {result.stdout}"


def test_workspace_env_in_dockerfile_steps(test_project):
    """Test that $WORKSPACE variable works correctly in Dockerfile steps."""
    # Modify config to use $WORKSPACE in a RUN step
    config_path = test_project / "cm.yaml"
    config_content = config_path.read_text()

    # Replace stages section with one that uses $WORKSPACE in a step
    new_config = config_content.replace(
        "stages:",
        """stages:""",
    )
    # Find base stage and add a step that verifies $WORKSPACE
    new_config = new_config.replace(
        "  base:",
        """  base:
    steps:
      - install_system_packages
      - RUN test -d ${WORKSPACE} && echo "WORKSPACE exists"
""",
    )

    config_path.write_text(new_config)

    # Regenerate and rebuild
    regen_result = subprocess.run(
        ["cm", "update"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert regen_result.returncode == 0, f"Update failed: {regen_result.stderr}"

    build_result = subprocess.run(
        ["just", "build"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    # Should succeed - the RUN step should complete without errors
    assert build_result.returncode == 0, f"Build failed: {build_result.stderr}"
