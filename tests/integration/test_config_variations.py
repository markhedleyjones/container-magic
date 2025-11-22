"""Integration tests for various YAML configurations.

Tests that different config variations generate valid files and work correctly.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

# Config fixtures to test
CONFIG_FIXTURES = [
    "minimal.yaml",
    "with_custom_commands.yaml",
    "with_env_vars.yaml",
    "with_gpu_features.yaml",
    "with_cached_assets.yaml",
]

# Linting tools (optional)
LINTERS = {
    "yamlfmt": shutil.which("yamlfmt"),
    "hadolint": shutil.which("hadolint"),
    "shellcheck": shutil.which("shellcheck"),
}


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


def validate_yaml(yaml_file: Path) -> tuple[bool, str]:
    """Validate YAML file with yamlfmt."""
    if not LINTERS["yamlfmt"]:
        return True, "yamlfmt not available"
    result = subprocess.run(
        [
            "yamlfmt",
            "-formatter",
            "retain_line_breaks=true",
            "-lint",
            str(yaml_file),
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0, result.stderr


def validate_dockerfile(dockerfile: Path) -> tuple[bool, str]:
    """Validate Dockerfile with hadolint."""
    if not LINTERS["hadolint"]:
        return True, "hadolint not available"
    result = subprocess.run(
        ["hadolint", "--failure-threshold", "error", str(dockerfile)],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0, result.stderr + result.stdout


def validate_shell_script(script: Path) -> tuple[bool, str]:
    """Validate shell script with shellcheck."""
    if not LINTERS["shellcheck"]:
        return True, "shellcheck not available"
    result = subprocess.run(
        ["shellcheck", str(script)],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0, result.stderr + result.stdout


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
        "Justfile",
        "build.sh",
        "run.sh",
    ]
    for file in expected_files:
        file_path = temp_project / file
        assert file_path.exists(), f"Missing file {file} for config {config_fixture}"

    # Validate config file
    valid, msg = validate_yaml(config_path)
    assert valid, f"YAML validation failed for {config_fixture}: {msg}"

    # Validate Dockerfile
    valid, msg = validate_dockerfile(temp_project / "Dockerfile")
    assert valid, f"Dockerfile validation failed for {config_fixture}: {msg}"

    # Validate build.sh
    valid, msg = validate_shell_script(temp_project / "build.sh")
    assert valid, f"build.sh validation failed for {config_fixture}: {msg}"

    # Validate run.sh
    valid, msg = validate_shell_script(temp_project / "run.sh")
    assert valid, f"run.sh validation failed for {config_fixture}: {msg}"


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
    files_to_check = ["Dockerfile", "Justfile", "build.sh", "run.sh"]
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


def test_custom_commands_execute_successfully(fixtures_dir, temp_project):
    """Test that custom commands can actually execute in a container."""
    # Use the config with custom commands
    fixture_path = fixtures_dir / "with_custom_commands.yaml"
    config_path = temp_project / "cm.yaml"
    shutil.copy(fixture_path, config_path)

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
    assert "Python 3.11" in result.stdout, "Python version check failed"


def test_env_vars_propagate_correctly(fixtures_dir, temp_project):
    """Test that environment variables are set correctly in containers."""
    # Use the config with env vars
    fixture_path = fixtures_dir / "with_env_vars.yaml"
    config_path = temp_project / "cm.yaml"
    shutil.copy(fixture_path, config_path)

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


def test_direct_script_execution(fixtures_dir, temp_project):
    """Test that direct script execution works (not just custom commands)."""
    # Use minimal config
    fixture_path = fixtures_dir / "minimal.yaml"
    config_path = temp_project / "cm.yaml"
    shutil.copy(fixture_path, config_path)

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

    # Execute script directly (run.sh defaults to WORKDIR/WORKSPACE for general commands)
    result = subprocess.run(
        ["./run.sh", "python test.py"],
        cwd=temp_project,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Direct script execution failed:\n{result.stderr}"
    assert "Direct execution works" in result.stdout


def test_linter_availability():
    """Display which linters are available (informational)."""
    print("\n=== Linter Availability ===")
    for name, path in LINTERS.items():
        status = "✓" if path else "✗"
        print(f"{status} {name}: {path or 'not found'}")
