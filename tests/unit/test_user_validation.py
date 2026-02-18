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

        assert "'base' uses 'become_user'" in stderr
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

        assert "become_user" in str(excinfo.value)
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


# --- Tests for lowercase `copy` step ---


def test_copy_after_switch_user_gets_chown():
    """Lowercase copy after switch_user should get --chown."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "user": {"production": {"name": "appuser"}},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "create_user",
                    "switch_user",
                    "copy docs/Gemfile /tmp/",
                ],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        capture_stderr(generate_dockerfile, config, output_path)
        content = output_path.read_text()
        assert "COPY --chown=${USER_UID}:${USER_GID} docs/Gemfile /tmp/" in content


def test_copy_before_switch_user_no_chown():
    """Lowercase copy before switch_user should not get --chown."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "user": {"production": {"name": "appuser"}},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "copy app /app",
                    "create_user",
                    "switch_user",
                ],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        capture_stderr(generate_dockerfile, config, output_path)
        content = output_path.read_text()
        # Should have plain COPY without --chown
        assert "COPY app /app" in content
        assert "--chown" not in content.split("COPY app /app")[0].split("\n")[-1]


def test_copy_after_switch_root_no_chown():
    """Lowercase copy after switch_root should not get --chown."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "user": {"production": {"name": "appuser"}},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "create_user",
                    "switch_user",
                    "switch_root",
                    "copy app /app",
                ],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        capture_stderr(generate_dockerfile, config, output_path)
        content = output_path.read_text()
        # Find the COPY line for app - should not have --chown
        for line in content.splitlines():
            if "COPY" in line and "app /app" in line:
                assert "--chown" not in line
                break
        else:
            pytest.fail("COPY app /app not found in Dockerfile")


def test_copy_inherits_user_from_parent():
    """Lowercase copy in child stage should inherit user context from parent ending with switch_user."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "user": {"production": {"name": "appuser"}},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "create_user",
                    "switch_user",
                ],
            },
            "development": {"from": "base", "steps": []},
            "production": {
                "from": "base",
                "steps": [
                    "copy app /app",
                ],
            },
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        capture_stderr(generate_dockerfile, config, output_path)
        content = output_path.read_text()
        assert "COPY --chown=${USER_UID}:${USER_GID} app /app" in content


def test_copy_parent_ends_with_switch_root():
    """Lowercase copy in child stage should not get --chown if parent ends with switch_root."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "user": {"production": {"name": "appuser"}},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "create_user",
                    "switch_user",
                    "switch_root",
                ],
            },
            "development": {"from": "base", "steps": []},
            "production": {
                "from": "base",
                "steps": [
                    "copy app /app",
                ],
            },
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        capture_stderr(generate_dockerfile, config, output_path)
        content = output_path.read_text()
        for line in content.splitlines():
            if "COPY" in line and "app /app" in line:
                assert "--chown" not in line
                break
        else:
            pytest.fail("COPY app /app not found in Dockerfile")


def test_uppercase_copy_unchanged():
    """Uppercase COPY (custom passthrough) should not get --chown even after switch_user."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "user": {"production": {"name": "appuser"}},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "create_user",
                    "switch_user",
                    "COPY app /app",
                ],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        capture_stderr(generate_dockerfile, config, output_path)
        content = output_path.read_text()
        # The uppercase COPY should pass through as-is (custom type)
        assert "COPY app /app" in content
        # Should NOT have --chown added
        for line in content.splitlines():
            if "COPY app /app" in line:
                assert "--chown" not in line
                break


def test_multiple_copy_steps_mixed_context():
    """Multiple copy steps should each reflect their position relative to user context changes."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "user": {"production": {"name": "appuser"}},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "copy config /etc/config",
                    "create_user",
                    "switch_user",
                    "copy app /home/appuser/app",
                    "switch_root",
                    "copy sysconfig /etc/sysconfig",
                ],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        capture_stderr(generate_dockerfile, config, output_path)
        content = output_path.read_text()

        # First copy: before switch_user → no --chown
        for line in content.splitlines():
            if "config /etc/config" in line:
                assert "--chown" not in line
                break
        else:
            pytest.fail("COPY config /etc/config not found")

        # Second copy: after switch_user → has --chown
        assert "COPY --chown=${USER_UID}:${USER_GID} app /home/appuser/app" in content

        # Third copy: after switch_root → no --chown
        for line in content.splitlines():
            if "sysconfig /etc/sysconfig" in line:
                assert "--chown" not in line
                break
        else:
            pytest.fail("COPY sysconfig /etc/sysconfig not found")


# --- Tests for become_user / become_root aliases ---


def test_become_user_alias_works():
    """become_user should work identically to switch_user."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "user": {"production": {"name": "appuser"}},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": ["create_user", "become_user"],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        capture_stderr(generate_dockerfile, config, output_path)
        content = output_path.read_text()
        assert "USER ${USER_NAME}" in content


def test_become_root_alias_works():
    """become_root should work identically to switch_root."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "user": {"production": {"name": "appuser"}},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": ["create_user", "become_user", "become_root"],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        capture_stderr(generate_dockerfile, config, output_path)
        content = output_path.read_text()
        assert "USER root" in content


def test_become_user_sets_copy_context():
    """copy after become_user should get --chown."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "user": {"production": {"name": "appuser"}},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "create_user",
                    "become_user",
                    "copy app /app",
                ],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        capture_stderr(generate_dockerfile, config, output_path)
        content = output_path.read_text()
        assert "COPY --chown=${USER_UID}:${USER_GID} app /app" in content


def test_become_root_clears_copy_context():
    """copy after become_root should not get --chown."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "user": {"production": {"name": "appuser"}},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "create_user",
                    "become_user",
                    "become_root",
                    "copy app /app",
                ],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        capture_stderr(generate_dockerfile, config, output_path)
        content = output_path.read_text()
        for line in content.splitlines():
            if "COPY" in line and "app /app" in line:
                assert "--chown" not in line
                break
        else:
            pytest.fail("COPY app /app not found in Dockerfile")


def test_parent_ends_with_become_user_inherits():
    """Child stage should inherit user context from parent ending with become_user."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "user": {"production": {"name": "appuser"}},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": ["create_user", "become_user"],
            },
            "development": {"from": "base", "steps": []},
            "production": {
                "from": "base",
                "steps": ["copy app /app"],
            },
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        capture_stderr(generate_dockerfile, config, output_path)
        content = output_path.read_text()
        assert "COPY --chown=${USER_UID}:${USER_GID} app /app" in content


# --- Tests for copy_as_user / copy_as_root ---


def test_copy_as_user_always_adds_chown():
    """copy_as_user should add --chown even in root context."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "user": {"production": {"name": "appuser"}},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "create_user",
                    "copy_as_user app /app",
                ],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        capture_stderr(generate_dockerfile, config, output_path)
        content = output_path.read_text()
        assert "COPY --chown=${USER_UID}:${USER_GID} app /app" in content


def test_copy_as_root_never_adds_chown():
    """copy_as_root should not add --chown even in user context."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "user": {"production": {"name": "appuser"}},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "create_user",
                    "become_user",
                    "copy_as_root config/sys.conf /etc/app/",
                ],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        capture_stderr(generate_dockerfile, config, output_path)
        content = output_path.read_text()
        for line in content.splitlines():
            if "COPY" in line and "config/sys.conf" in line:
                assert "--chown" not in line
                break
        else:
            pytest.fail("COPY config/sys.conf not found in Dockerfile")


def test_alpine_child_stage_uses_adduser():
    """Child stage inheriting from Alpine base should use adduser -D, not useradd, and -G with group name."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "user": {"production": {"name": "appuser"}},
        "stages": {
            "base": {
                "from": "alpine:3.19",
                "steps": ["create_user"],
            },
            "development": {
                "from": "base",
                "steps": ["become_user"],
            },
            "production": {
                "from": "base",
                "steps": ["become_user"],
            },
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        capture_stderr(generate_dockerfile, config, output_path)
        content = output_path.read_text()

        # Should use Alpine-style adduser, not useradd
        assert "adduser -D" in content
        assert "useradd" not in content

        # BusyBox adduser -G takes a group name, not a numeric GID
        assert "-G ${USER_NAME}" in content
        assert "-G ${USER_GID}" not in content


def test_copy_variants_mixed():
    """All copy variants should work together correctly."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "user": {"production": {"name": "appuser"}},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "create_user",
                    "copy_as_user early /home/appuser/early",
                    "become_user",
                    "copy app /home/appuser/app",
                    "copy_as_root config /etc/config",
                    "COPY raw /raw",
                ],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        capture_stderr(generate_dockerfile, config, output_path)
        content = output_path.read_text()

        # copy_as_user in root context → --chown
        assert (
            "COPY --chown=${USER_UID}:${USER_GID} early /home/appuser/early" in content
        )

        # copy in user context → --chown
        assert "COPY --chown=${USER_UID}:${USER_GID} app /home/appuser/app" in content

        # copy_as_root in user context → no --chown
        for line in content.splitlines():
            if "config /etc/config" in line:
                assert "--chown" not in line
                break
        else:
            pytest.fail("COPY config /etc/config not found")

        # Uppercase COPY → raw passthrough, no --chown
        for line in content.splitlines():
            if "raw /raw" in line:
                assert "--chown" not in line
                break
        else:
            pytest.fail("COPY raw /raw not found")


# --- Tests for --from= in copy steps ---


def test_copy_as_root_with_from():
    """copy_as_root --from=builder passes through as COPY --from=builder without --chown."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "user": {"production": {"name": "appuser"}},
        "stages": {
            "builder": {
                "from": "ubuntu:24.04",
                "steps": ["install_system_packages"],
            },
            "base": {
                "from": "ubuntu:24.04",
                "steps": [
                    "install_system_packages",
                    "copy_as_root --from=builder /usr/local/lib /usr/local/lib",
                ],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        capture_stderr(generate_dockerfile, config, output_path)
        content = output_path.read_text()
        assert "COPY --from=builder /usr/local/lib /usr/local/lib" in content


def test_copy_as_user_with_from():
    """copy_as_user --from=builder passes through with --chown prepended."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "user": {"production": {"name": "appuser"}},
        "stages": {
            "builder": {
                "from": "ubuntu:24.04",
                "steps": ["install_system_packages"],
            },
            "base": {
                "from": "ubuntu:24.04",
                "steps": [
                    "create_user",
                    "copy_as_user --from=builder /opt/app /home/appuser/app",
                ],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        capture_stderr(generate_dockerfile, config, output_path)
        content = output_path.read_text()
        # --chown comes first, then --from passes through in args
        assert (
            "COPY --chown=${USER_UID}:${USER_GID} --from=builder /opt/app /home/appuser/app"
            in content
        )


def test_copy_with_from_in_user_context():
    """copy --from=builder in user context passes through with --chown prepended."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "user": {"production": {"name": "appuser"}},
        "stages": {
            "builder": {
                "from": "ubuntu:24.04",
                "steps": [],
            },
            "base": {
                "from": "ubuntu:24.04",
                "steps": [
                    "create_user",
                    "become_user",
                    "copy --from=builder /opt/bin /home/appuser/bin",
                ],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        capture_stderr(generate_dockerfile, config, output_path)
        content = output_path.read_text()
        assert (
            "COPY --chown=${USER_UID}:${USER_GID} --from=builder /opt/bin /home/appuser/bin"
            in content
        )
