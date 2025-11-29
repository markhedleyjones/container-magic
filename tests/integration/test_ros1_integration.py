"""Test ROS1 project initialization and workspace mounting.

Note: This test demonstrates the workflow for a ROS1 project, but uses
ubuntu:20.04 instead of a full ROS image to avoid large image pull times
in the test environment.
"""

import subprocess
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def ros1_project():
    """Create a temporary ROS1-like test project."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        # Initialize a project using ubuntu:20.04 (lightweight alternative to ROS)
        # In real use, you would use: osrf/ros:noetic or osrf/ros:noetic-desktop
        init_result = subprocess.run(
            ["cm", "init", "ubuntu:20.04", "test-ros1-project"],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        assert init_result.returncode == 0, f"cm init failed: {init_result.stderr}"

        actual_project_dir = project_dir / "test-ros1-project"

        # Create a ROS1-like catkin workspace structure
        workspace_dir = actual_project_dir / "workspace"
        catkin_src = workspace_dir / "src"
        catkin_src.mkdir(parents=True, exist_ok=True)

        # Create a minimal ROS package
        package_dir = catkin_src / "test_package"
        package_dir.mkdir(exist_ok=True)

        # Create package.xml
        package_xml = package_dir / "package.xml"
        package_xml.write_text(
            """<?xml version="1.0"?>
<package format="2">
  <name>test_package</name>
  <version>0.0.0</version>
  <description>Test ROS1 package</description>
  <maintainer email="test@example.com">Test</maintainer>
  <license>BSD</license>
  <buildtool_depend>catkin</buildtool_depend>
</package>
"""
        )

        # Create CMakeLists.txt (simplified for ubuntu without ROS)
        cmakelists = package_dir / "CMakeLists.txt"
        cmakelists.write_text(
            """cmake_minimum_required(VERSION 3.0)
project(test_package)
message(STATUS "Building test_package")
"""
        )

        yield actual_project_dir


def test_ros1_init_and_build(ros1_project):
    """Test that ROS1-style project initializes and builds successfully."""
    # Build the image
    build_result = subprocess.run(
        ["just", "build"],
        cwd=ros1_project,
        capture_output=True,
        text=True,
    )
    assert build_result.returncode == 0, f"Build failed: {build_result.stderr}"


def test_ros1_workspace_accessible(ros1_project):
    """Test that WORKSPACE environment variable is properly set for ROS projects."""
    # Build the image first
    build_result = subprocess.run(
        ["just", "build"],
        cwd=ros1_project,
        capture_output=True,
        text=True,
    )
    assert build_result.returncode == 0, f"Build failed: {build_result.stderr}"

    # Get the workspace path
    result = subprocess.run(
        ["just", "run", "printenv WORKSPACE"],
        cwd=ros1_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Failed to get WORKSPACE: {result.stderr}"
    workspace_path = result.stdout.strip()
    assert workspace_path, "WORKSPACE should be set"

    # Verify workspace directory exists
    result = subprocess.run(
        ["just", "run", f"test -d {workspace_path} && echo OK"],
        cwd=ros1_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"WORKSPACE dir not found: {result.stderr}"
    assert "OK" in result.stdout


def test_ros1_workspace_mounted(ros1_project):
    """Test that the workspace directory is properly mounted in the container.

    This is critical for ROS development where you need to:
    1. Mount your catkin workspace
    2. Build packages with catkin_make
    3. Access build artifacts from the host
    """
    # Build the image first
    build_result = subprocess.run(
        ["just", "build"],
        cwd=ros1_project,
        capture_output=True,
        text=True,
    )
    assert build_result.returncode == 0, f"Build failed: {build_result.stderr}"

    # Get the workspace path
    result = subprocess.run(
        ["just", "run", "printenv WORKSPACE"],
        cwd=ros1_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    workspace_path = result.stdout.strip()

    # Verify src directory exists (the mounted workspace)
    result = subprocess.run(
        ["just", "run", f"test -d {workspace_path}/src && echo OK"],
        cwd=ros1_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Workspace src not mounted: {result.stderr}"
    assert "OK" in result.stdout

    # Verify package is accessible in the mounted workspace
    result = subprocess.run(
        ["just", "run", f"test -d {workspace_path}/src/test_package && echo OK"],
        cwd=ros1_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Package not accessible: {result.stderr}"
    assert "OK" in result.stdout

    # Verify package.xml is accessible
    result = subprocess.run(
        [
            "just",
            "run",
            f"test -f {workspace_path}/src/test_package/package.xml && echo OK",
        ],
        cwd=ros1_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"package.xml not accessible: {result.stderr}"
    assert "OK" in result.stdout
