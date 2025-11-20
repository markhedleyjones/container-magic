"""Tests for user-related validation in Dockerfile generation."""

import sys
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory


from container_magic.core.config import ContainerMagicConfig
from container_magic.generators.dockerfile import generate_dockerfile


def capture_stderr(func, *args, **kwargs):
    """Capture stderr output from a function."""
    old_stderr = sys.stderr
    sys.stderr = StringIO()
    try:
        func(*args, **kwargs)
        output = sys.stderr.getvalue()
        return output
    finally:
        sys.stderr = old_stderr


def test_user_defined_but_no_create_or_switch():
    """Warn if user is defined but neither create_user nor switch_user in build_steps."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "user": "myuser",  # User defined
                "build_steps": [
                    "install_system_packages",
                    # No create_user or switch_user!
                ],
            }
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        stderr = capture_stderr(generate_dockerfile, config, output_path)

        assert "user='myuser'" in stderr
        assert "has no 'create_user' or 'switch_user'" in stderr
        assert "will have no effect" in stderr


def test_switch_user_without_create_in_same_stage():
    """Warn if switch_user used but no create_user in same stage."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "user": "myuser",
                "build_steps": [
                    "switch_user",  # Trying to switch without creating
                ],
            }
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        stderr = capture_stderr(generate_dockerfile, config, output_path)

        assert "'base' uses 'switch_user'" in stderr
        assert "no 'create_user' found" in stderr
        assert "may fail at build time" in stderr


def test_switch_user_with_create_in_parent_stage():
    """No warning if switch_user used and create_user exists in parent stage."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "user": "myuser",
                "build_steps": [
                    "create_user",  # Create in base
                ],
            },
            "production": {
                "from": "base",  # Inherit from base
                "user": "myuser",
                "build_steps": [
                    "switch_user",  # Switch in production - should be OK
                ],
            },
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        stderr = capture_stderr(generate_dockerfile, config, output_path)

        # Should NOT warn about switch_user since create_user is in parent
        assert "uses 'switch_user'" not in stderr
        assert "may fail at build time" not in stderr


def test_create_user_and_switch_user_both_present():
    """No warning if both create_user and switch_user are present."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "user": "myuser",
                "build_steps": [
                    "create_user",
                    "switch_user",
                ],
            }
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        stderr = capture_stderr(generate_dockerfile, config, output_path)

        # Should not warn
        assert "Warning" not in stderr


def test_no_user_field_no_warnings():
    """No warnings if user field not defined."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "stages": {
            "base": {
                "from": "python:3-slim",
                # No user field
                "build_steps": [
                    "install_system_packages",
                ],
            }
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        stderr = capture_stderr(generate_dockerfile, config, output_path)

        # Should not warn
        assert "user=" not in stderr


def test_switch_root_no_validation_needed():
    """switch_root should not trigger any validation warnings."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "user": "myuser",
                "build_steps": [
                    "create_user",
                    "switch_root",  # Should not warn
                ],
            }
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        stderr = capture_stderr(generate_dockerfile, config, output_path)

        # Should not warn
        assert "Warning" not in stderr
