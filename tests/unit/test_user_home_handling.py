"""Tests for user and home path handling."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from container_magic.core.config import ContainerMagicConfig
from container_magic.generators.dockerfile import generate_dockerfile
from container_magic.generators.run_script import generate_run_script


def _generate_dockerfile(config_dict):
    """Generate a Dockerfile from a config dict and return its content."""
    config = ContainerMagicConfig(**config_dict)
    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        generate_dockerfile(config, output_path)
        return output_path.read_text()


def _generate_run_script(config_dict):
    """Generate a run.sh from a config dict and return its content."""
    config = ContainerMagicConfig(**config_dict)
    with TemporaryDirectory() as tmpdir:
        generate_run_script(config, Path(tmpdir))
        return (Path(tmpdir) / "run.sh").read_text()


# ---------------------------------------------------------------------------
# 2.1 user_cfg.name can be None
# ---------------------------------------------------------------------------


class TestUserNameNone:
    def test_production_user_without_name_raises_error(self):
        """A production user with uid/gid but no name should be rejected.

        Without this validation, the Dockerfile would contain literal
        USER_NAME=None and USER_HOME=/home/None.
        """
        with pytest.raises((ValueError, TypeError)):
            ContainerMagicConfig(
                **{
                    "project": {"name": "test", "workspace": "workspace"},
                    "user": {"production": {"uid": 1000, "gid": 1000}},
                    "stages": {
                        "base": {
                            "from": "python:3-slim",
                            "steps": ["create_user", "become_user"],
                        },
                        "development": {"from": "base", "steps": []},
                        "production": {"from": "base", "steps": []},
                    },
                }
            )


# ---------------------------------------------------------------------------
# 2.2 run.sh ignores custom home path
# ---------------------------------------------------------------------------


class TestRunScriptHomePath:
    def test_custom_home_used_in_run_script(self):
        """run.sh should use the custom home path, not /home/{name}."""
        config_dict = {
            "project": {"name": "test", "workspace": "workspace"},
            "user": {"production": {"name": "app", "home": "/opt/app"}},
            "stages": {
                "base": {
                    "from": "python:3-slim",
                    "steps": ["create_user"],
                },
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
            },
        }
        content = _generate_run_script(config_dict)
        assert "/opt/app" in content
        assert "/home/app" not in content

    def test_default_home_still_works(self):
        """When no custom home is set, /home/{name} should be used."""
        config_dict = {
            "project": {"name": "test", "workspace": "workspace"},
            "user": {"production": {"name": "app"}},
            "stages": {
                "base": {
                    "from": "python:3-slim",
                    "steps": ["create_user"],
                },
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
            },
        }
        content = _generate_run_script(config_dict)
        assert "/home/app" in content


# ---------------------------------------------------------------------------
# 2.3 UID/GID 0 treated as falsy
# ---------------------------------------------------------------------------


class TestUidGidZero:
    def test_uid_zero_not_overridden(self):
        """UID 0 should not be silently replaced with 1000.

        The `or` operator treats 0 as falsy, so `uid or 1000` gives 1000.
        """
        config_dict = {
            "project": {"name": "test", "workspace": "workspace"},
            "user": {"production": {"name": "specialroot", "uid": 0, "gid": 0}},
            "stages": {
                "base": {
                    "from": "python:3-slim",
                    "steps": ["create_user"],
                },
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
            },
        }
        content = _generate_dockerfile(config_dict)
        assert "USER_UID=0" in content
        assert "USER_GID=0" in content
        assert "USER_UID=1000" not in content
        assert "USER_GID=1000" not in content


# ---------------------------------------------------------------------------
# 2.4 to_yaml serialises steps
# ---------------------------------------------------------------------------


class TestToYamlStepsField:
    def test_to_yaml_uses_steps_key(self):
        """to_yaml should write 'steps' key."""
        config = ContainerMagicConfig(
            **{
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
        )
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "cm.yaml"
            config.to_yaml(output_path)
            content = output_path.read_text()
            assert "steps:" in content
