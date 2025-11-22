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


def test_production_user_empty_string():
    """Warn if create_user or switch_user used but production_user is not defined."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        # No production_user defined
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "create_user",  # Using create_user but no production_user
                ],
            },
            "development": {
                "from": "base",
                "steps": [],  # Prevent default development stage warnings
            },
            "production": {
                "from": "base",
                "steps": [],
            },
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        stderr = capture_stderr(generate_dockerfile, config, output_path)

        assert "production.user is not defined" in stderr
        assert "Define production.user" in stderr


def test_switch_user_without_create_in_same_stage():
    """Warn if switch_user used but no create_user in same stage."""
    config_dict = {
        "project": {
            "name": "test",
            "workspace": "workspace",
            "production_user": {"name": "myuser"},
        },
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "switch_user",  # Trying to switch without creating
                ],
            },
            "development": {"from": "base"},
            "production": {"from": "base"},
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
        "project": {
            "name": "test",
            "workspace": "workspace",
            "production_user": {"name": "myuser"},
        },
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "create_user",  # Create in base
                ],
            },
            "production": {
                "from": "base",  # Inherit from base
                "steps": [
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
        "project": {
            "name": "test",
            "workspace": "workspace",
            "production_user": {"name": "myuser"},
        },
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "create_user",
                    "switch_user",
                ],
            }
        },
        "development": {"from": "base"},
        "production": {"from": "base"},
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        stderr = capture_stderr(generate_dockerfile, config, output_path)

        # Should not warn
        assert "Warning" not in stderr


def test_no_user_keywords_no_warnings():
    """No warnings if no create_user or switch_user keywords used."""
    config_dict = {
        "project": {
            "name": "test",
            "workspace": "workspace",
            "production_user": {"name": "myuser"},
        },
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "install_system_packages",
                ],
            },
            "development": {
                "from": "base",
                "steps": [],
            },
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        stderr = capture_stderr(generate_dockerfile, config, output_path)

        # Should not warn
        assert "Warning" not in stderr


def test_switch_root_no_validation_needed():
    """switch_root should not trigger any validation warnings."""
    config_dict = {
        "project": {
            "name": "test",
            "workspace": "workspace",
            "production_user": {"name": "myuser"},
        },
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
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
