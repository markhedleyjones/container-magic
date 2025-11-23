"""Tests for standalone command script generation and execution."""

import subprocess

import pytest

from container_magic.core.config import ContainerMagicConfig
from container_magic.generators.standalone_commands import (
    generate_standalone_command_scripts,
)
from tests.utils.validation import validate_shell_script


@pytest.fixture
def config_with_standalone_commands():
    """Configuration with standalone commands enabled."""
    return ContainerMagicConfig(
        project={"name": "test-standalone", "workspace": "workspace"},
        stages={
            "base": {"from": "python:3.11-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
        commands={
            "train": {
                "command": "python workspace/train.py",
                "description": "Train the model",
                "standalone": True,
            },
            "test": {
                "command": "pytest workspace/tests",
                "description": "Run tests",
                "standalone": True,
                "env": {"PYTEST_OPTIONS": "-v"},
            },
            "serve": {
                "command": "python workspace/serve.py",
                "description": "Start server",
                "standalone": False,  # Should not generate script
            },
        },
    )


@pytest.fixture
def config_without_standalone():
    """Configuration without standalone commands."""
    return ContainerMagicConfig(
        project={"name": "test-no-standalone", "workspace": "workspace"},
        stages={
            "base": {"from": "python:3.11-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
        commands={
            "train": {"command": "python workspace/train.py", "description": "Train"},
        },
    )


def test_generate_standalone_scripts(tmp_path, config_with_standalone_commands):
    """Test that standalone scripts are generated for commands with standalone=True."""
    scripts = generate_standalone_command_scripts(
        config_with_standalone_commands, tmp_path
    )

    # Should generate 2 scripts (train and test, not serve)
    assert len(scripts) == 2

    # Check that scripts exist
    train_script = tmp_path / "train.sh"
    test_script = tmp_path / "test.sh"
    serve_script = tmp_path / "serve.sh"

    assert train_script.exists()
    assert test_script.exists()
    assert not serve_script.exists()

    # Check that scripts are executable
    assert train_script.stat().st_mode & 0o111  # Executable bits set
    assert test_script.stat().st_mode & 0o111


def test_standalone_script_content(tmp_path, config_with_standalone_commands):
    """Test that standalone scripts contain correct content."""
    generate_standalone_command_scripts(config_with_standalone_commands, tmp_path)

    train_script = tmp_path / "train.sh"
    content = train_script.read_text()

    # Check shebang
    assert content.startswith("#!/usr/bin/env bash")

    # Check project name
    assert 'IMAGE_NAME="test-standalone"' in content

    # Check command
    assert "python workspace/train.py" in content

    # Check description
    assert "# Train the model" in content


def test_standalone_script_with_env(tmp_path, config_with_standalone_commands):
    """Test that standalone scripts include environment variables."""
    generate_standalone_command_scripts(config_with_standalone_commands, tmp_path)

    test_script = tmp_path / "test.sh"
    content = test_script.read_text()

    # Check environment variable
    assert "PYTEST_OPTIONS=-v" in content
    assert 'RUN_ARGS+=("-e"' in content


def test_no_standalone_scripts_generated(tmp_path, config_without_standalone):
    """Test that no scripts are generated when standalone=False (default)."""
    scripts = generate_standalone_command_scripts(config_without_standalone, tmp_path)

    assert len(scripts) == 0
    assert not (tmp_path / "train.sh").exists()


def test_standalone_scripts_pass_shellcheck(tmp_path, config_with_standalone_commands):
    """Test that generated standalone scripts pass shellcheck validation."""
    generate_standalone_command_scripts(config_with_standalone_commands, tmp_path)

    train_script = tmp_path / "train.sh"
    test_script = tmp_path / "test.sh"

    # Validate with shellcheck
    train_result = validate_shell_script(train_script)
    test_result = validate_shell_script(test_script)

    assert train_result.passed, f"train.sh shellcheck failed: {train_result.message}"
    assert test_result.passed, f"test.sh shellcheck failed: {test_result.message}"


def test_standalone_script_syntax(tmp_path, config_with_standalone_commands):
    """Test that standalone scripts have valid bash syntax."""
    generate_standalone_command_scripts(config_with_standalone_commands, tmp_path)

    for script in [tmp_path / "train.sh", tmp_path / "test.sh"]:
        # Test syntax with bash -n
        result = subprocess.run(
            ["bash", "-n", str(script)], capture_output=True, text=True
        )
        assert result.returncode == 0, (
            f"{script.name} has syntax errors:\n{result.stderr}"
        )


def test_standalone_script_no_consecutive_blank_lines(
    tmp_path, config_with_standalone_commands
):
    """Test that standalone scripts have no excessive blank lines."""
    from tests.utils.validation import validate_no_consecutive_blank_lines

    generate_standalone_command_scripts(config_with_standalone_commands, tmp_path)

    train_script = tmp_path / "train.sh"
    result = validate_no_consecutive_blank_lines(train_script)

    assert result.passed, f"train.sh has excessive blank lines: {result.message}"


def test_standalone_commands_in_minimal_config(tmp_path):
    """Test standalone command generation with minimal configuration."""
    config = ContainerMagicConfig(
        project={"name": "minimal", "workspace": "workspace"},
        stages={
            "base": {"from": "ubuntu:22.04"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
        commands={
            "hello": {
                "command": "echo 'Hello World'",
                "standalone": True,
            }
        },
    )

    scripts = generate_standalone_command_scripts(config, tmp_path)

    assert len(scripts) == 1
    hello_script = tmp_path / "hello.sh"
    assert hello_script.exists()

    content = hello_script.read_text()
    assert "echo 'Hello World'" in content


def test_empty_commands_returns_empty_list(tmp_path):
    """Test that empty commands dict returns empty list."""
    config = ContainerMagicConfig(
        project={"name": "no-commands", "workspace": "workspace"},
        stages={
            "base": {"from": "python:3.11-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
    )

    scripts = generate_standalone_command_scripts(config, tmp_path)
    assert scripts == []


def test_orphaned_scripts_not_cleaned_up(tmp_path):
    """Test that old scripts are NOT automatically removed (user must clean up)."""
    # Create initial config with standalone train command
    config1 = ContainerMagicConfig(
        project={"name": "test-orphan", "workspace": "workspace"},
        stages={
            "base": {"from": "python:3.11-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
        commands={
            "train": {
                "command": "python workspace/train.py",
                "standalone": True,
            },
            "test": {
                "command": "pytest workspace/tests",
                "standalone": True,
            },
        },
    )

    # Generate scripts
    scripts = generate_standalone_command_scripts(config1, tmp_path)
    assert len(scripts) == 2
    assert (tmp_path / "train.sh").exists()
    assert (tmp_path / "test.sh").exists()

    # Change config: remove test command, make train non-standalone
    config2 = ContainerMagicConfig(
        project={"name": "test-orphan", "workspace": "workspace"},
        stages={
            "base": {"from": "python:3.11-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
        commands={
            "train": {
                "command": "python workspace/train.py",
                "standalone": False,  # Changed to non-standalone
            },
        },
    )

    # Regenerate - old scripts should still exist (not cleaned up)
    scripts = generate_standalone_command_scripts(config2, tmp_path)
    assert len(scripts) == 0
    # Old scripts remain - user is responsible for cleanup
    assert (tmp_path / "train.sh").exists()
    assert (tmp_path / "test.sh").exists()


def test_orphaned_scripts_when_command_removed(tmp_path):
    """Test that scripts remain when commands are removed (user cleanup)."""
    # Create config with standalone command
    config1 = ContainerMagicConfig(
        project={"name": "test-removed", "workspace": "workspace"},
        stages={
            "base": {"from": "python:3.11-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
        commands={
            "deploy": {
                "command": "bash workspace/deploy.sh",
                "standalone": True,
            },
        },
    )

    generate_standalone_command_scripts(config1, tmp_path)
    assert (tmp_path / "deploy.sh").exists()

    # Remove command entirely
    config2 = ContainerMagicConfig(
        project={"name": "test-removed", "workspace": "workspace"},
        stages={
            "base": {"from": "python:3.11-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
        commands={
            "serve": {
                "command": "python workspace/serve.py",
                "standalone": False,
            },
        },
    )

    generate_standalone_command_scripts(config2, tmp_path)
    # deploy.sh still exists - user must clean up
    assert (tmp_path / "deploy.sh").exists()
    # serve.sh not generated because standalone=false
    assert not (tmp_path / "serve.sh").exists()


def test_build_and_run_scripts_not_cleaned_up(tmp_path):
    """Test that build.sh and run.sh are never cleaned up."""
    # Create fake build.sh and run.sh
    (tmp_path / "build.sh").write_text("#!/bin/bash\necho build")
    (tmp_path / "run.sh").write_text("#!/bin/bash\necho run")

    # Create config with no commands
    config = ContainerMagicConfig(
        project={"name": "test-system", "workspace": "workspace"},
        stages={
            "base": {"from": "python:3.11-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
    )

    generate_standalone_command_scripts(config, tmp_path)

    # build.sh and run.sh should still exist
    assert (tmp_path / "build.sh").exists()
    assert (tmp_path / "run.sh").exists()


def test_unrelated_shell_scripts_not_deleted(tmp_path):
    """Test that unrelated .sh files are never deleted."""
    # Create some unrelated shell scripts
    (tmp_path / "install.sh").write_text("#!/bin/bash\necho installing")
    (tmp_path / "setup.sh").write_text("#!/bin/bash\necho setup")
    (tmp_path / "custom.sh").write_text("#!/bin/bash\necho custom")

    # Create config with a command named "train"
    config = ContainerMagicConfig(
        project={"name": "test-unrelated", "workspace": "workspace"},
        stages={
            "base": {"from": "python:3.11-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
        commands={
            "train": {
                "command": "python train.py",
                "standalone": True,
            },
        },
    )

    generate_standalone_command_scripts(config, tmp_path)

    # Unrelated scripts should still exist
    assert (tmp_path / "install.sh").exists()
    assert (tmp_path / "setup.sh").exists()
    assert (tmp_path / "custom.sh").exists()

    # train.sh should be generated
    assert (tmp_path / "train.sh").exists()
