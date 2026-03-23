"""Integration tests for various YAML configurations.

Tests that different config variations generate valid files and work correctly.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from tests.utils.validation import (
    validate_dockerfile,
    validate_no_consecutive_blank_lines,
    validate_shell_script,
    validate_yaml,
)

# Config fixtures to test
CONFIG_FIXTURES = [
    "minimal.yaml",
    "with_custom_commands.yaml",
    "with_env_vars.yaml",
    "with_gpu_features.yaml",
    "with_assets.yaml",
    "with_custom_stage.yaml",
    "with_mounts.yaml",
]


@pytest.fixture
def fixtures_dir():
    """Return path to config fixtures directory."""
    return Path(__file__).parent.parent / "fixtures" / "configs"


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project directory."""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    workspace_dir = project_dir / "workspace"
    workspace_dir.mkdir()
    return project_dir


@pytest.mark.parametrize("config_fixture", CONFIG_FIXTURES)
def test_config_generates_valid_files(config_fixture, fixtures_dir, temp_project):
    """Test that each config fixture generates valid files."""
    # Copy fixture config to project
    fixture_path = fixtures_dir / config_fixture
    config_path = temp_project / "cm.yaml"
    shutil.copy(fixture_path, config_path)

    # Generate files
    result = subprocess.run(
        ["cm", "update"],
        cwd=temp_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"cm update failed for {config_fixture}:\n{result.stderr}"
    )

    # Check all expected files exist
    expected_files = [
        "Dockerfile",
        "build.sh",
        "run.sh",
    ]
    for file in expected_files:
        file_path = temp_project / file
        assert file_path.exists(), f"Missing file {file} for config {config_fixture}"

    # Justfile should NOT be generated in v3
    assert not (temp_project / "Justfile").exists(), (
        f"Justfile should not be generated in v3 for config {config_fixture}"
    )

    # Validate config file
    result = validate_yaml(config_path)
    assert result, f"YAML validation failed for {config_fixture}: {result}"

    # Validate Dockerfile
    result = validate_dockerfile(temp_project / "Dockerfile")
    assert result, f"Dockerfile validation failed for {config_fixture}: {result}"

    # Validate Dockerfile has no consecutive blank lines
    result = validate_no_consecutive_blank_lines(temp_project / "Dockerfile")
    assert result, f"Dockerfile has consecutive blank lines: {result}"

    # Validate build.sh
    result = validate_shell_script(temp_project / "build.sh")
    assert result, f"build.sh validation failed for {config_fixture}: {result}"

    result = validate_no_consecutive_blank_lines(temp_project / "build.sh")
    assert result, f"build.sh has consecutive blank lines: {result}"

    # Validate run.sh
    result = validate_shell_script(temp_project / "run.sh")
    assert result, f"run.sh validation failed for {config_fixture}: {result}"

    result = validate_no_consecutive_blank_lines(temp_project / "run.sh")
    assert result, f"run.sh has consecutive blank lines: {result}"


@pytest.mark.parametrize("config_fixture", CONFIG_FIXTURES)
def test_config_regenerates_idempotently(config_fixture, fixtures_dir, temp_project):
    """Test that regenerating from same config produces identical results."""
    # Copy fixture config
    fixture_path = fixtures_dir / config_fixture
    config_path = temp_project / "cm.yaml"
    shutil.copy(fixture_path, config_path)

    # First generation
    result = subprocess.run(
        ["cm", "update"],
        cwd=temp_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Read generated files
    files_to_check = ["Dockerfile", "build.sh", "run.sh"]
    first_gen = {}
    for filename in files_to_check:
        first_gen[filename] = (temp_project / filename).read_text()

    # Second generation
    result = subprocess.run(
        ["cm", "update"],
        cwd=temp_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Compare files
    for filename in files_to_check:
        second_content = (temp_project / filename).read_text()
        assert first_gen[filename] == second_content, (
            f"Regeneration not idempotent for {filename} in {config_fixture}"
        )


def test_custom_commands_execute_successfully(fixtures_dir, temp_project, debian_base_image):
    """Test that custom commands can actually execute in a container."""
    # Use the config with custom commands
    fixture_path = fixtures_dir / "with_custom_commands.yaml"
    config_path = temp_project / "cm.yaml"
    shutil.copy(fixture_path, config_path)

    # Replace base image with locally-built cm-test:debian (has Python installed)
    config_content = config_path.read_text().replace(
        "debian:bookworm-slim", "cm-test:debian"
    )
    config_path.write_text(config_content)

    # Generate files
    result = subprocess.run(
        ["cm", "update"],
        cwd=temp_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Build the production image
    result = subprocess.run(
        ["./build.sh"],
        cwd=temp_project,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, f"build.sh failed:\n{result.stderr}"

    # Test the 'test' command
    result = subprocess.run(
        ["./run.sh", "test"],
        cwd=temp_project,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Custom command 'test' failed:\n{result.stderr}"
    assert "Hello from test command" in result.stdout, "Custom command output incorrect"

    # Test the 'version' command
    result = subprocess.run(
        ["./run.sh", "version"],
        cwd=temp_project,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Custom command 'version' failed:\n{result.stderr}"
    assert "Python 3" in result.stdout, "Python version check failed"


def test_env_vars_propagate_correctly(fixtures_dir, temp_project, debian_base_image):
    """Test that environment variables are set correctly in containers."""
    # Use the config with env vars
    fixture_path = fixtures_dir / "with_env_vars.yaml"
    config_path = temp_project / "cm.yaml"
    shutil.copy(fixture_path, config_path)

    # Replace base image with locally-built cm-test:debian (has Python installed)
    config_content = config_path.read_text().replace(
        "debian:bookworm-slim", "cm-test:debian"
    )
    config_path.write_text(config_content)

    # Generate files
    result = subprocess.run(
        ["cm", "update"],
        cwd=temp_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Build the production image
    result = subprocess.run(
        ["./build.sh"],
        cwd=temp_project,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, f"build.sh failed:\n{result.stderr}"

    # Test the env-check command
    result = subprocess.run(
        ["./run.sh", "env-check"],
        cwd=temp_project,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"env-check command failed:\n{result.stderr}"

    # Verify environment variables are present
    assert "DATABASE_URL" in result.stdout
    assert "API_KEY" in result.stdout
    assert "LOG_LEVEL" in result.stdout


def test_direct_script_execution(fixtures_dir, temp_project, debian_base_image):
    """Test that direct script execution works (not just custom commands)."""
    # Use minimal config
    fixture_path = fixtures_dir / "minimal.yaml"
    config_path = temp_project / "cm.yaml"
    shutil.copy(fixture_path, config_path)

    # Replace base image with locally-built cm-test:debian (has Python installed)
    config_content = config_path.read_text().replace(
        "debian:bookworm-slim", "cm-test:debian"
    )
    config_path.write_text(config_content)

    # Create a test script in workspace BEFORE building
    test_script = temp_project / "workspace" / "test.py"
    test_script.write_text("print('Direct execution works')\n")

    # Generate files
    result = subprocess.run(
        ["cm", "update"],
        cwd=temp_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Build the production image (now it will include test.py)
    result = subprocess.run(
        ["./build.sh"],
        cwd=temp_project,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, f"build.sh failed:\n{result.stderr}"

    # Execute script directly (exec form: each argument separate)
    result = subprocess.run(
        ["./run.sh", "python3", "test.py"],
        cwd=temp_project,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Direct script execution failed:\n{result.stderr}"
    assert "Direct execution works" in result.stdout


def test_production_workspace_permissions(fixtures_dir, temp_project, debian_base_image):
    """Test that workspace is copied into production image with correct permissions."""
    # Use minimal config
    fixture_path = fixtures_dir / "minimal.yaml"
    config_path = temp_project / "cm.yaml"
    shutil.copy(fixture_path, config_path)

    # Replace base image with locally-built cm-test:debian (has Python installed)
    config_content = config_path.read_text().replace(
        "debian:bookworm-slim", "cm-test:debian"
    )
    config_path.write_text(config_content)

    # Create test files in workspace
    test_file = temp_project / "workspace" / "test_file.txt"
    test_file.write_text("test content\n")

    # Generate files
    result = subprocess.run(
        ["cm", "update"],
        cwd=temp_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Build production image (build.sh targets production by default)
    result = subprocess.run(
        ["./build.sh"],
        cwd=temp_project,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, f"build.sh failed:\n{result.stderr}"

    # Verify workspace exists in image
    # Shell variable expansion and && require explicit bash -c (exec form)
    result = subprocess.run(
        ["./run.sh", "bash", "-c", "ls -la ${WORKSPACE}"],
        cwd=temp_project,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Workspace check failed:\n{result.stderr}"
    assert "test_file.txt" in result.stdout, (
        "Workspace file not found in production image"
    )

    # Verify file ownership (production workspace should be root-owned for security)
    result = subprocess.run(
        ["./run.sh", "bash", "-c", "stat -c '%U:%G' ${WORKSPACE}/test_file.txt"],
        cwd=temp_project,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"File ownership check failed:\n{result.stderr}"
    assert "root:root" in result.stdout, (
        f"File ownership incorrect. Expected root:root, got: {result.stdout}"
    )

    # Verify the workspace is read-only for the non-root user (immutable code)
    result = subprocess.run(
        [
            "./run.sh",
            "bash",
            "-c",
            "touch ${WORKSPACE}/test_write.txt 2>&1 || echo 'Write denied'",
        ],
        cwd=temp_project,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "Write denied" in result.stdout or "Permission denied" in result.stdout, (
        "Workspace should be read-only in production, but write succeeded"
    )


def test_image_tagging_by_target(fixtures_dir, temp_project, debian_base_image):
    """Test that images are tagged correctly: default 'latest' and --tag override."""
    # Use config with custom stage
    fixture_path = fixtures_dir / "with_custom_stage.yaml"
    config_path = temp_project / "cm.yaml"
    shutil.copy(fixture_path, config_path)

    # Replace base image with locally-built cm-test:debian (has Python installed)
    config_content = config_path.read_text().replace(
        "debian:bookworm-slim", "cm-test:debian"
    )
    config_path.write_text(config_content)

    # Generate files
    result = subprocess.run(
        ["cm", "update"],
        cwd=temp_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Detect which runtime is available (same logic as build.sh: prefer docker)
    if shutil.which("docker"):
        runtime = "docker"
    elif shutil.which("podman"):
        runtime = "podman"
    else:
        pytest.skip("Neither docker nor podman found")

    # Test 1: Default build - should be tagged as 'latest'
    result = subprocess.run(
        ["./build.sh"],
        cwd=temp_project,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, f"Default build failed:\n{result.stderr}"
    assert "test-custom-stage:latest" in result.stdout, (
        "Default build should be tagged as 'latest'"
    )

    # Verify image exists with latest tag
    result = subprocess.run(
        [
            runtime,
            "images",
            "--format",
            "{{.Repository}}:{{.Tag}}",
            "test-custom-stage",
        ],
        capture_output=True,
        text=True,
    )
    assert "test-custom-stage:latest" in result.stdout

    # Test 2: Build with --tag override
    result = subprocess.run(
        ["./build.sh", "--tag", "v1.0.0"],
        cwd=temp_project,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, f"Tagged build failed:\n{result.stderr}"
    assert "test-custom-stage:v1.0.0" in result.stdout, (
        "Build with --tag should use the specified tag"
    )

    # Verify image exists with custom tag
    result = subprocess.run(
        [
            runtime,
            "images",
            "--format",
            "{{.Repository}}:{{.Tag}}",
            "test-custom-stage",
        ],
        capture_output=True,
        text=True,
    )
    assert "test-custom-stage:v1.0.0" in result.stdout

    # Cleanup - remove test images
    subprocess.run(
        [
            runtime,
            "rmi",
            "test-custom-stage:latest",
            "test-custom-stage:v1.0.0",
        ],
        capture_output=True,
    )


def test_volumes_and_devices_appear_in_generated_files(fixtures_dir, temp_project):
    """Test that runtime volumes and devices appear in run.sh."""
    fixture_path = fixtures_dir / "with_mounts.yaml"
    config_path = temp_project / "cm.yaml"
    shutil.copy(fixture_path, config_path)

    result = subprocess.run(
        ["cm", "update"],
        cwd=temp_project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"cm update failed:\n{result.stderr}"

    run_sh = (temp_project / "run.sh").read_text()
    assert '"-v" "/tmp/test-data:/data:ro"' in run_sh
    assert '"-v" "/var/log/app:/logs"' in run_sh
    assert '"--device" "/dev/ttyUSB0"' in run_sh
