"""Integration tests for custom commands feature."""

import subprocess

import pytest


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary directory for CLI tests."""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    return project_dir


def test_custom_commands_in_justfile_and_run_sh(temp_project_dir):
    """Test that custom commands are generated in both Justfile and run.sh."""
    # Initialize a basic project
    result = subprocess.run(
        ["cm", "init", "--here", "--compact", "python"],
        cwd=temp_project_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"cm init failed: {result.stderr}"

    # Add custom commands to the config
    config_file = temp_project_dir / "cm.yaml"
    config_content = config_file.read_text()

    # Add custom commands section
    custom_commands = """
commands:
  daemon:
    command: "python workspace/daemon.py"
    description: "Run the daemon process"
  test:
    command: "pytest workspace/tests"
    description: "Run tests"
    env:
      PYTEST_ARGS: "-v"
"""
    config_file.write_text(config_content + custom_commands)

    # Regenerate files
    result = subprocess.run(
        ["cm", "update"],
        cwd=temp_project_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"cm update failed: {result.stderr}"

    # Check Justfile has custom commands
    justfile_content = (temp_project_dir / "Justfile").read_text()
    assert "# Custom Commands" in justfile_content, (
        "Justfile missing custom commands section"
    )
    assert "# Run the daemon process" in justfile_content, (
        "Justfile missing daemon description"
    )
    assert "daemon:" in justfile_content, "Justfile missing daemon command"
    assert "python workspace/daemon.py" in justfile_content, (
        "Justfile missing daemon command implementation"
    )
    assert "# Run tests" in justfile_content, "Justfile missing test description"
    assert "test:" in justfile_content, "Justfile missing test command"
    assert "pytest workspace/tests" in justfile_content, (
        "Justfile missing test command implementation"
    )
    assert "PYTEST_ARGS" in justfile_content and "-v" in justfile_content, (
        "Justfile missing test env vars"
    )

    # Check run.sh has custom commands
    run_sh_content = (temp_project_dir / "run.sh").read_text()
    assert "# Custom command handlers" in run_sh_content, (
        "run.sh missing custom command handlers section"
    )
    assert "run_daemon()" in run_sh_content, "run.sh missing daemon function"
    assert "# Run the daemon process" in run_sh_content, (
        "run.sh missing daemon description"
    )
    assert "python workspace/daemon.py" in run_sh_content, (
        "run.sh missing daemon command"
    )
    assert "run_test()" in run_sh_content, "run.sh missing test function"
    assert "# Run tests" in run_sh_content, "run.sh missing test description"
    assert "pytest workspace/tests" in run_sh_content, "run.sh missing test command"
    assert "PYTEST_ARGS" in run_sh_content, "run.sh missing test env vars"

    # Check run.sh has case statement to dispatch commands
    assert 'case "$1" in' in run_sh_content, "run.sh missing case statement"
    assert "daemon)" in run_sh_content, "run.sh missing daemon case"
    assert "test)" in run_sh_content, "run.sh missing test case"


def test_custom_commands_with_no_description(temp_project_dir):
    """Test that custom commands work without descriptions."""
    # Initialize a basic project
    result = subprocess.run(
        ["cm", "init", "--here", "--compact", "python"],
        cwd=temp_project_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"cm init failed: {result.stderr}"

    # Add custom command without description
    config_file = temp_project_dir / "cm.yaml"
    config_content = config_file.read_text()

    custom_commands = """
commands:
  serve:
    command: "python -m http.server 8000"
"""
    config_file.write_text(config_content + custom_commands)

    # Regenerate files
    result = subprocess.run(
        ["cm", "update"],
        cwd=temp_project_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"cm update failed: {result.stderr}"

    # Check both files have the command
    justfile_content = (temp_project_dir / "Justfile").read_text()
    assert "serve:" in justfile_content, "Justfile missing serve command"
    assert "python -m http.server 8000" in justfile_content, (
        "Justfile missing serve command implementation"
    )

    run_sh_content = (temp_project_dir / "run.sh").read_text()
    assert "run_serve()" in run_sh_content, "run.sh missing serve function"
    assert "python -m http.server 8000" in run_sh_content, (
        "run.sh missing serve command"
    )


def test_no_custom_commands_section_when_empty(temp_project_dir):
    """Test that custom command sections are not added when no commands are defined."""
    # Initialize a basic project (no custom commands)
    result = subprocess.run(
        ["cm", "init", "--here", "--compact", "python"],
        cwd=temp_project_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"cm init failed: {result.stderr}"

    # Check Justfile doesn't have custom commands section
    justfile_content = (temp_project_dir / "Justfile").read_text()
    assert "# Custom Commands" not in justfile_content, (
        "Justfile should not have custom commands section when none defined"
    )

    # Check run.sh doesn't have custom command handlers
    run_sh_content = (temp_project_dir / "run.sh").read_text()
    assert "# Custom command handlers" not in run_sh_content, (
        "run.sh should not have custom command handlers when none defined"
    )
    assert 'case "$1" in' not in run_sh_content, (
        "run.sh should not have case statement when no custom commands"
    )


def test_custom_commands_use_workdir_not_workspace(temp_project_dir):
    """Test that custom commands use WORKDIR (not WORKDIR/WORKSPACE) as working directory."""
    # Initialize project
    result = subprocess.run(
        ["cm", "init", "--here", "--compact", "python"],
        cwd=temp_project_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"cm init failed: {result.stderr}"

    # Add custom command
    config_file = temp_project_dir / "cm.yaml"
    config_content = config_file.read_text()

    custom_commands = """
commands:
  daemon:
    command: "python workspace/daemon.py"
    description: "Run daemon"
"""
    config_file.write_text(config_content + custom_commands)

    # Regenerate
    result = subprocess.run(
        ["cm", "update"],
        cwd=temp_project_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"cm update failed: {result.stderr}"

    # Check run.sh uses WORKDIR (not WORKDIR/WORKSPACE) for custom commands
    run_sh_content = (temp_project_dir / "run.sh").read_text()

    # Should use -w "${WORKDIR}" not -w "${WORKDIR}/${WORKSPACE_NAME}" in custom commands
    # Look for the pattern in the run_daemon function
    import re

    daemon_match = re.search(
        r"run_daemon\(\).*?^\}", run_sh_content, re.MULTILINE | re.DOTALL
    )
    assert daemon_match, "Could not find run_daemon function"
    daemon_function = daemon_match.group(0)

    assert '-w "${WORKDIR}"' in daemon_function, (
        "Custom command should use WORKDIR as working directory"
    )
    assert '-w "${WORKDIR}/${WORKSPACE_NAME}"' not in daemon_function, (
        "Custom command should not use WORKDIR/WORKSPACE"
    )


def test_run_sh_shellcheck_validation_with_commands(temp_project_dir):
    """Test that run.sh with custom commands passes shellcheck validation."""
    import shutil

    if not shutil.which("shellcheck"):
        pytest.skip("shellcheck not available")

    # Initialize project
    result = subprocess.run(
        ["cm", "init", "--here", "--compact", "python"],
        cwd=temp_project_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"cm init failed: {result.stderr}"

    # Add custom commands
    config_file = temp_project_dir / "cm.yaml"
    config_content = config_file.read_text()

    custom_commands = """
commands:
  daemon:
    command: "python workspace/daemon.py"
    description: "Run daemon"
    env:
      LOG_LEVEL: "debug"
"""
    config_file.write_text(config_content + custom_commands)

    # Regenerate
    result = subprocess.run(
        ["cm", "update"],
        cwd=temp_project_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"cm update failed: {result.stderr}"

    # Validate with shellcheck
    run_sh = temp_project_dir / "run.sh"
    result = subprocess.run(
        ["shellcheck", str(run_sh)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"shellcheck failed for run.sh:\n{result.stdout}\n{result.stderr}"
    )


def test_commands_with_workspace_variable(temp_project_dir):
    """Test that commands with $WORKSPACE variable expand in container."""
    # Initialize project
    result = subprocess.run(
        ["cm", "init", "--here", "--compact", "python"],
        cwd=temp_project_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"cm init failed: {result.stderr}"

    # Add custom commands with $WORKSPACE variable
    config_file = temp_project_dir / "cm.yaml"
    config_content = config_file.read_text()

    custom_commands = """
commands:
  build:
    command: "$WORKSPACE/scripts/build.sh"
    description: "Build the project"
  test:
    command: "bash -c 'source $WORKSPACE/setup.sh && pytest'"
    description: "Run tests with setup"
"""
    config_file.write_text(config_content + custom_commands)

    # Regenerate
    result = subprocess.run(
        ["cm", "update"],
        cwd=temp_project_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"cm update failed: {result.stderr}"

    # Check run.sh has escaped dollar signs
    run_sh_content = (temp_project_dir / "run.sh").read_text()
    assert r"\$WORKSPACE/scripts/build.sh" in run_sh_content, (
        "run.sh should have escaped $WORKSPACE in build command"
    )
    assert r"source \$WORKSPACE/setup.sh" in run_sh_content, (
        "run.sh should have escaped $WORKSPACE in test command"
    )

    # Check Justfile also has escaped dollar signs
    justfile_content = (temp_project_dir / "Justfile").read_text()
    assert r"\$WORKSPACE/scripts/build.sh" in justfile_content, (
        "Justfile should have escaped $WORKSPACE in build command"
    )


def test_custom_commands_mount_workspace_in_justfile(temp_project_dir):
    """Test that custom commands in Justfile mount the workspace directory."""
    # Initialize project
    result = subprocess.run(
        ["cm", "init", "--here", "--compact", "python"],
        cwd=temp_project_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"cm init failed: {result.stderr}"

    # Add custom command
    config_file = temp_project_dir / "cm.yaml"
    config_content = config_file.read_text()

    custom_commands = '\ncommands:\n  build:\n    command: "$WORKSPACE/scripts/build.sh"\n    description: "Build the project"\n'
    config_file.write_text(config_content + custom_commands)

    # Regenerate
    result = subprocess.run(
        ["cm", "update"],
        cwd=temp_project_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"cm update failed: {result.stderr}"

    # Check Justfile has workspace mount in custom command
    justfile_content = (temp_project_dir / "Justfile").read_text()

    # Custom commands section should be present
    assert "# Custom Commands" in justfile_content, (
        "Justfile should have custom commands section"
    )
    assert "\nbuild:" in justfile_content, "Justfile should have build command"

    # Should have workspace mount in custom command
    # The workspace mount should be in the custom command section
    assert 'RUN_ARGS+=("-v"' in justfile_content, (
        "Custom command should have volume mount with -v flag"
    )
    # Check that the mount includes the workspace name from the config
    # which is "workspace" for default compact python config
    assert "$(pwd)/workspace:$(echo ~)/workspace:z" in justfile_content, (
        "Workspace mount should map local workspace directory"
    )


def test_custom_commands_quote_escaping_in_justfile(temp_project_dir):
    """Test that custom commands with nested quotes are properly escaped in Justfile."""
    # Initialize a basic project
    result = subprocess.run(
        ["cm", "init", "--here", "--compact", "python"],
        cwd=temp_project_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"cm init failed: {result.stderr}"

    # Add custom command with nested quotes (bash -c "...")
    config_file = temp_project_dir / "cm.yaml"
    config_content = config_file.read_text()

    custom_commands = """
commands:
  build:
    command: "bash -c \\"cd $WORKSPACE && python setup.py build\\""
    description: "Build the project"
"""
    config_file.write_text(config_content + custom_commands)

    # Regenerate files
    result = subprocess.run(
        ["cm", "update"],
        cwd=temp_project_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"cm update failed: {result.stderr}"

    # Check Justfile has properly escaped quotes in the COMMAND variable
    justfile_content = (temp_project_dir / "Justfile").read_text()

    # The COMMAND line should have escaped inner quotes
    assert (
        'COMMAND="bash -c \\"cd \\$WORKSPACE && python setup.py build\\""'
        in justfile_content
    ), "Justfile custom command should have escaped inner quotes"

    # Verify the generated script would be syntactically valid bash
    # Extract the build recipe from the Justfile
    import re

    build_match = re.search(
        r"^build:\n(    #!/usr/bin/env bash\n.*?)(?=\n^[a-z]|\Z)",
        justfile_content,
        re.MULTILINE | re.DOTALL,
    )
    if build_match:
        build_script = build_match.group(1)
        # Save to temp file and check syntax
        script_file = temp_project_dir / "build_test.sh"
        script_file.write_text("#!/usr/bin/env bash\n" + build_script)
        result = subprocess.run(
            ["bash", "-n", str(script_file)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Generated build script has syntax error: {result.stderr}"
        )
