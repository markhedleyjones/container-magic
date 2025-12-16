"""Test ROS1 (noetic) project initialization and catkin_make workflow."""

import subprocess
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def ros1_project():
    """Create a temporary ROS1 catkin workspace project."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        # Initialize with actual ROS1 Noetic image
        init_result = subprocess.run(
            ["cm", "init", "docker.io/osrf/ros:noetic", "test-ros1-project"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if init_result.returncode != 0:
            # Fallback: manually create the minimal config if cm init fails
            actual_project_dir = project_dir / "test-ros1-project"
            actual_project_dir.mkdir(exist_ok=True)

            # Create minimal container-magic.yaml
            config_content = """project:
  name: test-ros1-project
  workspace: workspace
  auto_update: false

user:
  development:
    host: true
  production:
    name: user

runtime:
  backend: auto
  privileged: false
  features: []

stages:
  base:
    from: docker.io/osrf/ros:noetic
    packages:
      apt: []
      pip: []
    env: {}
    cached_assets: []
    build_steps:
      - create_user
  development:
    from: base
    packages:
      apt: []
      pip: []
    env: {}
    cached_assets: []
    build_steps:
      - switch_user
  production:
    from: base
    packages:
      apt: []
      pip: []
    env: {}
    cached_assets: []

commands: {}

build_script:
  default_target: production
"""
            config_file = actual_project_dir / "container-magic.yaml"
            config_file.write_text(config_content)

            # Generate Justfile and Dockerfile
            gen_result = subprocess.run(
                ["cm", "update"],
                cwd=actual_project_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if gen_result.returncode != 0:
                raise RuntimeError(f"Failed to generate files: {gen_result.stderr}")

            # Create workspace directory
            workspace_dir = actual_project_dir / "workspace"
            workspace_dir.mkdir(exist_ok=True)
        else:
            actual_project_dir = project_dir / "test-ros1-project"

        # Create a proper ROS1 catkin workspace structure
        workspace_dir = actual_project_dir / "workspace"
        catkin_src = workspace_dir / "src"
        catkin_src.mkdir(parents=True, exist_ok=True)

        # Create a minimal ROS package
        package_dir = catkin_src / "test_package"
        package_dir.mkdir(exist_ok=True)

        # Create package.xml for ROS1
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
  <depend>roscpp</depend>
</package>
"""
        )

        # Create CMakeLists.txt for catkin
        cmakelists = package_dir / "CMakeLists.txt"
        cmakelists.write_text(
            """cmake_minimum_required(VERSION 2.8.3)
project(test_package)

find_package(catkin REQUIRED COMPONENTS
  roscpp
)

catkin_package()
"""
        )

        yield actual_project_dir


def test_ros1_init_and_build_image(ros1_project):
    """Test that ROS1 image builds successfully."""
    build_result = subprocess.run(
        ["just", "build"],
        cwd=ros1_project,
        capture_output=True,
        text=True,
        timeout=600,  # 10 minutes for building ROS image
    )
    # Skip test if image is not available (registry issues, network problems, etc)
    if (
        "manifest unknown" in build_result.stderr
        or "toomanyrequests" in build_result.stderr
    ):
        pytest.skip(f"ROS1 image not available: {build_result.stderr}")
    assert build_result.returncode == 0, f"Build failed: {build_result.stderr}"


def test_ros1_catkin_make(ros1_project):
    """Test that catkin_make works in the ROS1 container with WORKSPACE."""
    # Build the image first
    build_result = subprocess.run(
        ["just", "build"],
        cwd=ros1_project,
        capture_output=True,
        text=True,
        timeout=600,
    )
    # Skip test if image is not available (registry issues, network problems, etc)
    if (
        "manifest unknown" in build_result.stderr
        or "toomanyrequests" in build_result.stderr
    ):
        pytest.skip(f"ROS1 image not available: {build_result.stderr}")
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

    # Run catkin_make in the workspace
    result = subprocess.run(
        [
            "just",
            "run",
            f"bash -c 'source /opt/ros/noetic/setup.bash && cd {workspace_path} && catkin_make'",
        ],
        cwd=ros1_project,
        capture_output=True,
        text=True,
        timeout=300,  # 5 minutes for catkin_make
    )
    assert result.returncode == 0, (
        f"catkin_make failed:\nstderr: {result.stderr}\nstdout: {result.stdout}"
    )

    # Verify build artifacts were created
    result = subprocess.run(
        [
            "just",
            "run",
            f"test -d {workspace_path}/build && test -d {workspace_path}/devel && echo OK",
        ],
        cwd=ros1_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Build artifacts not found: {result.stderr}"
    assert "OK" in result.stdout


def test_ros1_workspace_mounted(ros1_project):
    """Test that the catkin workspace is properly mounted and accessible.

    This is critical for ROS development - you need to:
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
        timeout=600,
    )
    # Skip test if image is not available (registry issues, network problems, etc)
    if (
        "manifest unknown" in build_result.stderr
        or "toomanyrequests" in build_result.stderr
    ):
        pytest.skip(f"ROS1 image not available: {build_result.stderr}")
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

    # Verify ROS package is accessible in the mounted workspace
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

    # Verify CMakeLists.txt is accessible
    result = subprocess.run(
        [
            "just",
            "run",
            f"test -f {workspace_path}/src/test_package/CMakeLists.txt && echo OK",
        ],
        cwd=ros1_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"CMakeLists.txt not accessible: {result.stderr}"
    assert "OK" in result.stdout
