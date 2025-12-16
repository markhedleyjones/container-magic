"""Tests for user-related validation in Dockerfile generation."""

import sys
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

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
    """Error if create_user or switch_user used but production_user is not defined."""
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

        # Should raise ValueError
        with pytest.raises(ValueError) as excinfo:
            generate_dockerfile(config, output_path)

        assert "production.user is not defined" in str(excinfo.value)


def test_switch_user_without_create_in_same_stage():
    """Warn if switch_user used but no create_user in same stage."""
    config_dict = {
        "project": {
            "name": "test",
            "workspace": "workspace",
        },
        "user": {
            "production": {"name": "myuser"},
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
        },
        "user": {
            "production": {"name": "myuser"},
        },
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "create_user",  # Create in base
                ],
            },
            "development": {
                "from": "base",
                "steps": [],
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
        },
        "user": {
            "production": {"name": "myuser"},
        },
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "create_user",
                    "switch_user",
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

        # Should not warn
        assert "Warning" not in stderr


def test_no_user_keywords_no_warnings():
    """No warnings if no create_user or switch_user keywords used."""
    config_dict = {
        "project": {
            "name": "test",
            "workspace": "workspace",
        },
        "user": {
            "production": {"name": "myuser"},
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

        # Should not warn
        assert "Warning" not in stderr


def test_switch_root_no_validation_needed():
    """switch_root should not trigger any validation warnings."""
    config_dict = {
        "project": {
            "name": "test",
            "workspace": "workspace",
        },
        "user": {
            "production": {"name": "myuser"},
        },
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "create_user",
                    "switch_root",  # Should not warn
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

        # Should not warn
        assert "Warning" not in stderr


def test_no_user_config_no_default_create_user():
    """When no user is configured, create_user should not be added to default steps."""
    config_dict = {
        "project": {
            "name": "test",
            "workspace": "workspace",
            # No production_user or any user config
        },
        "stages": {
            "base": {
                "from": "python:3-slim",
                # No explicit steps, should use defaults
            },
            "development": {
                "from": "base",
                "steps": [],
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

        # Should not produce any warnings or errors
        assert "Warning" not in stderr
        assert "Error" not in stderr
        assert "not defined" not in stderr

        # Check that Dockerfile doesn't have USER directive (since no user was configured)
        dockerfile_content = output_path.read_text()
        # Should not have create_user step for root user (no USER directives for root)
        # The USER_UID, USER_GID args should not be needed if user is root
        assert "USER_UID" not in dockerfile_content or "root" in dockerfile_content


def test_explicit_create_user_without_user_config_raises_error():
    """Explicitly using create_user without user config should raise an error."""
    config_dict = {
        "project": {
            "name": "test",
            "workspace": "workspace",
            # No production_user defined
        },
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "create_user",  # Explicit but no user config
                ],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"

        # Should raise ValueError
        with pytest.raises(ValueError) as excinfo:
            generate_dockerfile(config, output_path)

        assert "create_user" in str(excinfo.value)
        assert "production.user is not defined" in str(excinfo.value)


def test_explicit_switch_user_without_user_config_raises_error():
    """Explicitly using switch_user without user config should raise an error."""
    config_dict = {
        "project": {
            "name": "test",
            "workspace": "workspace",
            # No production_user defined
        },
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "create_user",  # Need create_user first
                ],
            },
            "development": {
                "from": "base",
                "steps": [
                    "switch_user",  # Explicit but no user config
                ],
            },
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"

        # Should raise ValueError
        with pytest.raises(ValueError) as excinfo:
            generate_dockerfile(config, output_path)

        assert "switch_user" in str(excinfo.value)
        assert "production.user is not defined" in str(excinfo.value)


def test_user_defined_but_never_used():
    """User config defined but never used in create_user or switch_user steps."""
    config_dict = {
        "project": {
            "name": "test",
            "workspace": "workspace",
        },
        "user": {
            "production": {"name": "appuser"},  # User defined
        },
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "install_system_packages",  # No create_user step
                ],
            },
            "development": {
                "from": "base",
                "steps": [],
            },
            "production": {
                "from": "base",
                "steps": [],  # No switch_user step
            },
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        stderr = capture_stderr(generate_dockerfile, config, output_path)

        # Should not error - it's OK to define a user and not use it in create_user/switch_user
        # The user args ARE included because they're referenced in WORKDIR
        dockerfile_content = output_path.read_text()
        assert "USER_NAME=appuser" in dockerfile_content
        assert "Warning" not in stderr
        assert "Error" not in stderr


def test_user_config_with_only_name():
    """User config with only name uses default uid/gid (1000/1000)."""
    config_dict = {
        "project": {
            "name": "test",
            "workspace": "workspace",
        },
        "user": {
            "production": {"name": "appuser"},  # Only name specified
        },
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": ["create_user"],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        stderr = capture_stderr(generate_dockerfile, config, output_path)

        dockerfile_content = output_path.read_text()
        # Should use default 1000 for both uid and gid
        assert "USER_UID=1000" in dockerfile_content
        assert "USER_GID=1000" in dockerfile_content
        assert "USER_NAME=appuser" in dockerfile_content
        assert "Warning" not in stderr
        assert "Error" not in stderr


def test_user_config_with_only_uid():
    """User config with only name and uid uses default gid (1000)."""
    config_dict = {
        "project": {
            "name": "test",
            "workspace": "workspace",
        },
        "user": {
            "production": {
                "name": "appuser",
                "uid": 2000,  # Custom uid
                # gid not specified, should default to 1000
            },
        },
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": ["create_user"],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        stderr = capture_stderr(generate_dockerfile, config, output_path)

        dockerfile_content = output_path.read_text()
        assert "USER_UID=2000" in dockerfile_content
        assert "USER_GID=1000" in dockerfile_content  # Default
        assert "USER_NAME=appuser" in dockerfile_content
        assert "Warning" not in stderr
        assert "Error" not in stderr


def test_user_config_with_only_gid():
    """User config with only name and gid uses default uid (1000)."""
    config_dict = {
        "project": {
            "name": "test",
            "workspace": "workspace",
        },
        "user": {
            "production": {
                "name": "appuser",
                # uid not specified, should default to 1000
                "gid": 3000,  # Custom gid
            },
        },
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": ["create_user"],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        stderr = capture_stderr(generate_dockerfile, config, output_path)

        dockerfile_content = output_path.read_text()
        assert "USER_UID=1000" in dockerfile_content  # Default
        assert "USER_GID=3000" in dockerfile_content
        assert "USER_NAME=appuser" in dockerfile_content
        assert "Warning" not in stderr
        assert "Error" not in stderr


def test_user_config_with_custom_home():
    """User config with custom home directory."""
    config_dict = {
        "project": {
            "name": "test",
            "workspace": "workspace",
        },
        "user": {
            "production": {
                "name": "appuser",
                "uid": 2000,
                "gid": 3000,
                "home": "/opt/appuser",  # Custom home
            },
        },
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": ["create_user"],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        stderr = capture_stderr(generate_dockerfile, config, output_path)

        dockerfile_content = output_path.read_text()
        assert "USER_UID=2000" in dockerfile_content
        assert "USER_GID=3000" in dockerfile_content
        assert "USER_NAME=appuser" in dockerfile_content
        assert "USER_HOME=/opt/appuser" in dockerfile_content
        assert "Warning" not in stderr
        assert "Error" not in stderr


def test_user_config_default_home_path():
    """User config without home uses /home/{name} by default."""
    config_dict = {
        "project": {
            "name": "test",
            "workspace": "workspace",
        },
        "user": {
            "production": {
                "name": "appuser",
                # home not specified, should default to /home/appuser
            },
        },
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": ["create_user"],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        stderr = capture_stderr(generate_dockerfile, config, output_path)

        dockerfile_content = output_path.read_text()
        # Should use default /home/appuser
        assert "USER_HOME=/home/appuser" in dockerfile_content
        assert "Warning" not in stderr
        assert "Error" not in stderr
