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


def test_create_user_without_user_config_raises():
    """Error if create_user used but no user section is defined."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
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

        # Should raise ValueError
        with pytest.raises(ValueError) as excinfo:
            generate_dockerfile(config, output_path)

        assert "no user is configured" in str(excinfo.value)


def test_become_user_without_create_in_same_stage():
    """Warn if become_user used but no create_user in same stage."""
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
                    "become_user",  # Trying to switch without creating
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


def test_become_user_with_create_in_parent_stage():
    """No warning if become_user used and create_user exists in parent stage."""
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
                    "become_user",  # Switch in production - should be OK
                ],
            },
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        stderr = capture_stderr(generate_dockerfile, config, output_path)

        # Should NOT warn about become_user since create_user is in parent
        assert "uses 'become_user'" not in stderr
        assert "may fail at build time" not in stderr


def test_create_user_and_become_user_both_present():
    """No warning if both create_user and become_user are present."""
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
                    "become_user",
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
    """No warnings if no create_user or become_user keywords used."""
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
                    {"run": "echo test"},
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


def test_become_root_no_validation_needed():
    """become_root should not trigger any validation warnings."""
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
                    "become_root",  # Should not warn
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
        assert "no user is configured" in str(excinfo.value)


def test_explicit_become_user_without_user_config_raises_error():
    """Explicitly using become_user without user config should raise an error."""
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
                    "become_user",  # Explicit but no user config
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

        assert "no user is configured" in str(excinfo.value)


def test_user_defined_but_never_used():
    """User config defined but never used in create_user or become_user steps."""
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
                    {"run": "echo test"},  # No create_user step
                ],
            },
            "development": {
                "from": "base",
                "steps": [],
            },
            "production": {
                "from": "base",
                "steps": [],  # No become_user step
            },
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        stderr = capture_stderr(generate_dockerfile, config, output_path)

        # Should not error - it's OK to define a user and not use it
        # User ARGs only appear in stages that have user-related steps
        dockerfile_content = output_path.read_text()
        assert "USER_NAME=appuser" not in dockerfile_content
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


def test_copy_after_become_user_gets_chown():
    """Lowercase copy after become_user should get --chown."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "user": {"production": {"name": "appuser"}},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "create_user",
                    "become_user",
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


def test_copy_before_become_user_no_chown():
    """Lowercase copy before become_user should not get --chown."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "user": {"production": {"name": "appuser"}},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "copy app /app",
                    "create_user",
                    "become_user",
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


def test_copy_after_become_root_no_chown():
    """Lowercase copy after become_root should not get --chown."""
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
        # Find the COPY line for app - should not have --chown
        for line in content.splitlines():
            if "COPY" in line and "app /app" in line:
                assert "--chown" not in line
                break
        else:
            pytest.fail("COPY app /app not found in Dockerfile")


def test_copy_inherits_user_from_parent():
    """Lowercase copy in child stage should inherit user context from parent ending with become_user."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "user": {"production": {"name": "appuser"}},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "create_user",
                    "become_user",
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


def test_copy_parent_ends_with_become_root():
    """Lowercase copy in child stage should not get --chown if parent ends with become_root."""
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
    """Uppercase COPY (custom passthrough) should not get --chown even after become_user."""
    config_dict = {
        "project": {"name": "test", "workspace": "workspace"},
        "user": {"production": {"name": "appuser"}},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "create_user",
                    "become_user",
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
                    "become_user",
                    "copy app /home/appuser/app",
                    "become_root",
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

        # First copy: before become_user → no --chown
        for line in content.splitlines():
            if "config /etc/config" in line:
                assert "--chown" not in line
                break
        else:
            pytest.fail("COPY config /etc/config not found")

        # Second copy: after become_user → has --chown
        assert "COPY --chown=${USER_UID}:${USER_GID} app /home/appuser/app" in content

        # Third copy: after become_root → no --chown
        for line in content.splitlines():
            if "sysconfig /etc/sysconfig" in line:
                assert "--chown" not in line
                break
        else:
            pytest.fail("COPY sysconfig /etc/sysconfig not found")


# --- Tests for become_user / become_root ---


def test_become_user_produces_user_directive():
    """become_user should produce USER directive."""
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


def test_become_root_produces_user_root_directive():
    """become_root should produce USER root directive."""
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
                "steps": [],
            },
            "base": {
                "from": "ubuntu:24.04",
                "steps": [
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
                "steps": [],
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
