"""Tests for user-related validation in Dockerfile generation."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from container_magic.core.config import ContainerMagicConfig
from container_magic.generators.dockerfile import generate_dockerfile


def test_no_user_keywords_no_warnings(capsys):
    """No warnings if no create or become steps used."""
    config_dict = {
        "names": {"project": "test", "workspace": "workspace", "user": "root"},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [{"run": "echo test"}],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        generate_dockerfile(config, output_path)
        captured = capsys.readouterr()
        assert "Warning" not in captured.err


def test_become_root_no_validation_needed(capsys):
    """become: root should not trigger any validation warnings."""
    config_dict = {
        "names": {"project": "test", "workspace": "workspace", "user": "myuser"},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    {"create": "user"},
                    {"become": "root"},
                ],
            },
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        generate_dockerfile(config, output_path)
        captured = capsys.readouterr()
        assert "Warning" not in captured.err


def test_no_create_user_no_user_args(capsys):
    """When no create_user step exists, user ARGs should not appear."""
    config_dict = {
        "names": {"project": "test", "workspace": "workspace", "user": "root"},
        "stages": {
            "base": {"from": "python:3-slim"},
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        generate_dockerfile(config, output_path)
        captured = capsys.readouterr()
        assert "Warning" not in captured.err
        assert "Error" not in captured.err

        dockerfile_content = output_path.read_text()
        assert "USER_UID" not in dockerfile_content or "root" in dockerfile_content


def test_create_user_with_defaults():
    """create: user uses default uid/gid (1000/1000)."""
    config_dict = {
        "names": {"project": "test", "workspace": "workspace", "user": "appuser"},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [{"create": "user"}],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        generate_dockerfile(config, output_path)

        dockerfile_content = output_path.read_text()
        assert "USER_UID=1000" in dockerfile_content
        assert "USER_GID=1000" in dockerfile_content
        assert "USER_NAME=appuser" in dockerfile_content


def test_create_user_default_home_path():
    """create: user uses /home/{name} as default home."""
    config_dict = {
        "names": {"project": "test", "workspace": "workspace", "user": "appuser"},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [{"create": "user"}],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        generate_dockerfile(config, output_path)

        dockerfile_content = output_path.read_text()
        assert "USER_HOME=/home/appuser" in dockerfile_content


# --- Tests for lowercase copy step ---


def test_copy_after_become_user_gets_chown():
    """Lowercase copy after become gets --chown with username."""
    config_dict = {
        "names": {"project": "test", "workspace": "workspace", "user": "appuser"},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    {"create": "user"},
                    {"become": "user"},
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
        generate_dockerfile(config, output_path)
        content = output_path.read_text()
        assert "COPY --chown=${USER_NAME}:${USER_NAME} docs/Gemfile /tmp/" in content


def test_copy_before_become_no_chown():
    """Lowercase copy before become should not get --chown."""
    config_dict = {
        "names": {"project": "test", "workspace": "workspace", "user": "appuser"},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "copy app /app",
                    {"create": "user"},
                    {"become": "user"},
                ],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        generate_dockerfile(config, output_path)
        content = output_path.read_text()
        assert "COPY app /app" in content
        assert "--chown" not in content.split("COPY app /app")[0].split("\n")[-1]


def test_copy_after_become_root_no_chown():
    """Lowercase copy after become: root should not get --chown."""
    config_dict = {
        "names": {"project": "test", "workspace": "workspace", "user": "appuser"},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    {"create": "user"},
                    {"become": "user"},
                    {"become": "root"},
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
        generate_dockerfile(config, output_path)
        content = output_path.read_text()
        for line in content.splitlines():
            if "COPY" in line and "app /app" in line:
                assert "--chown" not in line
                break
        else:
            pytest.fail("COPY app /app not found in Dockerfile")


def test_copy_inherits_user_from_parent():
    """Lowercase copy in child stage should inherit user context from parent."""
    config_dict = {
        "names": {"project": "test", "workspace": "workspace", "user": "appuser"},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    {"create": "user"},
                    {"become": "user"},
                ],
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
        generate_dockerfile(config, output_path)
        content = output_path.read_text()
        assert "COPY --chown=${USER_NAME}:${USER_NAME} app /app" in content


def test_copy_parent_ends_with_become_root():
    """Lowercase copy in child stage should not get --chown if parent ends with become: root."""
    config_dict = {
        "names": {"project": "test", "workspace": "workspace", "user": "appuser"},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    {"create": "user"},
                    {"become": "user"},
                    {"become": "root"},
                ],
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
        generate_dockerfile(config, output_path)
        content = output_path.read_text()
        for line in content.splitlines():
            if "COPY" in line and "app /app" in line:
                assert "--chown" not in line
                break
        else:
            pytest.fail("COPY app /app not found in Dockerfile")


def test_uppercase_copy_unchanged():
    """Uppercase COPY should not get --chown even after become."""
    config_dict = {
        "names": {"project": "test", "workspace": "workspace", "user": "appuser"},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    {"create": "user"},
                    {"become": "user"},
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
        generate_dockerfile(config, output_path)
        content = output_path.read_text()
        assert "COPY app /app" in content
        for line in content.splitlines():
            if "COPY app /app" in line:
                assert "--chown" not in line
                break


def test_multiple_copy_steps_mixed_context():
    """Multiple copy steps should each reflect their position relative to user context changes."""
    config_dict = {
        "names": {"project": "test", "workspace": "workspace", "user": "appuser"},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    "copy config /etc/config",
                    {"create": "user"},
                    {"become": "user"},
                    "copy app /home/appuser/app",
                    {"become": "root"},
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
        generate_dockerfile(config, output_path)
        content = output_path.read_text()

        # First copy: before become - no --chown
        for line in content.splitlines():
            if "config /etc/config" in line:
                assert "--chown" not in line
                break
        else:
            pytest.fail("COPY config /etc/config not found")

        # Second copy: after become - has --chown with username
        assert "COPY --chown=${USER_NAME}:${USER_NAME} app /home/appuser/app" in content

        # Third copy: after become: root - no --chown
        for line in content.splitlines():
            if "sysconfig /etc/sysconfig" in line:
                assert "--chown" not in line
                break
        else:
            pytest.fail("COPY sysconfig /etc/sysconfig not found")


# --- Tests for become ---


def test_become_produces_user_directive():
    """become should produce USER directive with the username."""
    config_dict = {
        "names": {"project": "test", "workspace": "workspace", "user": "appuser"},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [{"create": "user"}, {"become": "user"}],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        generate_dockerfile(config, output_path)
        content = output_path.read_text()
        assert "USER ${USER_NAME}" in content


def test_become_root_produces_user_root_directive():
    """become: root should produce USER root directive."""
    config_dict = {
        "names": {"project": "test", "workspace": "workspace", "user": "appuser"},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [
                    {"create": "user"},
                    {"become": "user"},
                    {"become": "root"},
                ],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        generate_dockerfile(config, output_path)
        content = output_path.read_text()
        assert "USER root" in content


def test_become_arbitrary_user():
    """become with an arbitrary username should produce correct USER directive."""
    config_dict = {
        "names": {"project": "test", "workspace": "workspace", "user": "root"},
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [{"become": "www-data"}],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        generate_dockerfile(config, output_path)
        content = output_path.read_text()
        assert "USER www-data" in content


def test_alpine_child_stage_uses_adduser():
    """Child stage inheriting from Alpine base should use adduser -D."""
    config_dict = {
        "names": {"project": "test", "workspace": "workspace", "user": "appuser"},
        "stages": {
            "base": {
                "from": "alpine:3.19",
                "steps": [{"create": "user"}],
            },
            "development": {
                "from": "base",
                "steps": [{"become": "user"}],
            },
            "production": {
                "from": "base",
                "steps": [{"become": "user"}],
            },
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        generate_dockerfile(config, output_path)
        content = output_path.read_text()

        assert "adduser -D" in content
        assert "useradd" not in content
        assert "-G ${USER_NAME}" in content
        assert "-G ${USER_GID}" not in content


# --- Tests for --from= in copy steps ---


def test_copy_with_from_in_root_context():
    """copy --from=builder in root context has no --chown."""
    config_dict = {
        "names": {"project": "test", "workspace": "workspace", "user": "root"},
        "stages": {
            "builder": {"from": "ubuntu:24.04", "steps": []},
            "base": {
                "from": "ubuntu:24.04",
                "steps": [
                    "copy --from=builder /usr/local/lib /usr/local/lib",
                ],
            },
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config = ContainerMagicConfig(**config_dict)

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        generate_dockerfile(config, output_path)
        content = output_path.read_text()
        assert "COPY --from=builder /usr/local/lib /usr/local/lib" in content


def test_copy_with_from_in_user_context():
    """copy --from=builder in user context passes through with --chown prepended."""
    config_dict = {
        "names": {"project": "test", "workspace": "workspace", "user": "appuser"},
        "stages": {
            "builder": {"from": "ubuntu:24.04", "steps": []},
            "base": {
                "from": "ubuntu:24.04",
                "steps": [
                    {"create": "user"},
                    {"become": "user"},
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
        generate_dockerfile(config, output_path)
        content = output_path.read_text()
        assert (
            "COPY --chown=${USER_NAME}:${USER_NAME} --from=builder /opt/bin /home/appuser/bin"
            in content
        )
