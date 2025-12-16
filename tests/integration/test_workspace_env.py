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
    """Test that $WORKSPACE env var is properly set in the container."""
    # Build the image
    build_result = subprocess.run(
        ["just", "build"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert build_result.returncode == 0, f"Build failed: {build_result.stderr}"

    # Test 1: Verify $WORKSPACE variable exists and is set
    # Use printenv which doesn't rely on shell variable expansion
    result = subprocess.run(
        ["just", "run", "printenv WORKSPACE"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Command failed: {result.stderr}"
    workspace_path = result.stdout.strip()
    assert workspace_path, "WORKSPACE variable is empty or not set"
    assert "/" in workspace_path, f"WORKSPACE path looks invalid: {workspace_path}"

    # Test 2: Verify the workspace directory actually exists
    result = subprocess.run(
        ["just", "run", f"test -d {workspace_path} && echo OK"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"WORKSPACE directory does not exist at {workspace_path}: {result.stderr}"
    )
    assert "OK" in result.stdout, "Directory test failed"

    # Test 3: Verify workspace file is accessible
    result = subprocess.run(
        ["just", "run", f"test -f {workspace_path}/test.txt && echo OK"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Failed to access file via WORKSPACE: {result.stderr}"
    )

    # Test 4: Verify $WORKSPACE path is consistent (same in multiple invocations)
    result1 = subprocess.run(
        ["just", "run", "printenv WORKSPACE"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    result2 = subprocess.run(
        ["just", "run", "printenv WORKSPACE"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert result1.stdout.strip() == result2.stdout.strip(), (
        f"WORKSPACE path changed: {result1.stdout.strip()} vs {result2.stdout.strip()}"
    )

    # Test 5: Verify workspace contents are accessible
    result = subprocess.run(
        ["just", "run", f"ls {workspace_path}/"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Failed to list workspace: {result.stderr}"
    assert "test.txt" in result.stdout, (
        f"test.txt not found in workspace listing: {result.stdout}"
    )


def test_workspace_env_with_custom_command(test_project):
    """Test that WORKSPACE is available and usable in the container."""
    # Build the image first
    build_result = subprocess.run(
        ["just", "build"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert build_result.returncode == 0, f"Build failed: {build_result.stderr}"

    # Get the workspace path
    result = subprocess.run(
        ["just", "run", "printenv WORKSPACE"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Failed to get WORKSPACE: {result.stderr}"
    workspace_path = result.stdout.strip()
    assert workspace_path, "WORKSPACE should be set"

    # Verify file exists in workspace
    result = subprocess.run(
        ["just", "run", f"test -f {workspace_path}/test.txt && echo OK"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"WORKSPACE test failed: {result.stderr}"
    assert "OK" in result.stdout, f"Test file not found: {result.stdout}"


def test_workspace_env_in_dockerfile_steps(test_project):
    """Test that WORKSPACE variable is available and properly configured."""
    # Build the image first
    build_result = subprocess.run(
        ["just", "build"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert build_result.returncode == 0, f"Build failed: {build_result.stderr}"

    # Verify WORKSPACE is set and accessible
    result = subprocess.run(
        ["just", "run", "printenv WORKSPACE"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Failed to get WORKSPACE: {result.stderr}"
    workspace_path = result.stdout.strip()

    # Verify the WORKSPACE directory exists
    result = subprocess.run(
        ["just", "run", f"test -d {workspace_path} && echo OK"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"WORKSPACE directory not accessible: {result.stderr}"
    )
    assert "OK" in result.stdout
