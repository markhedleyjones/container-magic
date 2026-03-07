"""Tests for user and home path handling."""

from pathlib import Path
from tempfile import TemporaryDirectory


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
# 2.2 run.sh uses user home path
# ---------------------------------------------------------------------------


class TestRunScriptHomePath:
    def test_default_home_works(self):
        """When create_user is used, /home/{name} should be used."""
        config_dict = {
            "project": {"name": "test", "workspace": "workspace"},
            "stages": {
                "base": {
                    "from": "python:3-slim",
                    "steps": [{"create_user": "app"}],
                },
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
            },
        }
        content = _generate_run_script(config_dict)
        assert "/home/app" in content


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
                        "steps": [{"create_user": "app"}],
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
