"""Tests for conda/mamba/micromamba step support and registry field expansion."""

import pytest

from container_magic.core.registry import load_registry
from container_magic.core.steps import parse_step


@pytest.fixture
def registry():
    return load_registry()


class TestCondaInstall:
    def test_default_channel_is_conda_forge(self, registry):
        step = {"conda": {"install": ["pytorch", "whisperx"]}}
        result = parse_step(step, registry)
        command = result["command"]
        assert command.startswith("conda install")
        assert "--yes --quiet --override-channels" in command
        assert "--channel conda-forge" in command
        assert "pytorch" in command
        assert "whisperx" in command

    def test_explicit_channels_replace_default(self, registry):
        step = {
            "conda": {
                "install": ["pytorch"],
                "channels": ["pytorch", "nvidia", "conda-forge"],
            }
        }
        result = parse_step(step, registry)
        command = result["command"]
        assert "--channel pytorch" in command
        assert "--channel nvidia" in command
        assert "--channel conda-forge" in command
        # Order matters (priority)
        assert (
            command.index("--channel pytorch")
            < command.index("--channel nvidia")
            < command.index("--channel conda-forge")
        )

    def test_default_channel_not_duplicated_when_explicit(self, registry):
        step = {
            "conda": {
                "install": ["pytorch"],
                "channels": ["custom"],
            }
        }
        result = parse_step(step, registry)
        command = result["command"]
        assert "--channel custom" in command
        assert "--channel conda-forge" not in command

    def test_single_channel(self, registry):
        step = {
            "conda": {
                "install": ["pytorch"],
                "channels": ["pytorch"],
            }
        }
        result = parse_step(step, registry)
        command = result["command"]
        assert command.count("--channel") == 1
        assert "--channel pytorch" in command

    def test_override_channels_flag_baked_in(self, registry):
        """--override-channels is part of the default flags so .condarc is ignored."""
        step = {"conda": {"install": ["pytorch"]}}
        result = parse_step(step, registry)
        assert "--override-channels" in result["command"]

    def test_unknown_field_raises_helpful_error(self, registry):
        step = {
            "conda": {
                "install": ["pytorch"],
                "chanel": ["conda-forge"],  # typo
            }
        }
        with pytest.raises(ValueError, match="Unknown field"):
            parse_step(step, registry)

    def test_unknown_field_error_lists_valid_fields(self, registry):
        step = {
            "conda": {
                "install": ["pytorch"],
                "bogus": [],
            }
        }
        with pytest.raises(ValueError, match="Valid fields: channels"):
            parse_step(step, registry)


class TestMambaAndMicromamba:
    def test_mamba_uses_same_defaults(self, registry):
        step = {"mamba": {"install": ["pytorch"]}}
        result = parse_step(step, registry)
        command = result["command"]
        assert command.startswith("mamba install")
        assert "--channel conda-forge" in command

    def test_micromamba_uses_same_defaults(self, registry):
        step = {"micromamba": {"install": ["pytorch"]}}
        result = parse_step(step, registry)
        command = result["command"]
        assert command.startswith("micromamba install")
        assert "--channel conda-forge" in command

    def test_mamba_accepts_channels(self, registry):
        step = {
            "mamba": {
                "install": ["pytorch"],
                "channels": ["pytorch", "conda-forge"],
            }
        }
        result = parse_step(step, registry)
        command = result["command"]
        assert "--channel pytorch" in command
        assert "--channel conda-forge" in command


class TestBackwardCompatibility:
    def test_pip_still_works_without_fields(self, registry):
        """pip has no fields declared; existing usage is unchanged."""
        step = {"pip": {"install": ["flask"]}}
        result = parse_step(step, registry)
        command = result["command"]
        assert command.startswith("pip install --no-cache-dir")
        assert "flask" in command

    def test_apt_get_still_works(self, registry):
        step = {"apt-get": {"install": ["curl"]}}
        result = parse_step(step, registry)
        command = result["command"]
        assert "apt-get update" in command
        assert "apt-get install" in command
        assert "curl" in command
        assert "rm -rf /var/lib/apt/lists/*" in command


class TestProjectOverride:
    def test_project_can_override_conda_flags(self):
        registry = load_registry(
            project_overrides={
                "conda": {
                    "install": {
                        "flags": "--yes --verbose",
                    }
                }
            }
        )
        step = {"conda": {"install": ["pytorch"]}}
        result = parse_step(step, registry)
        command = result["command"]
        assert "--verbose" in command
        # Project override replaces the whole entry, so default channel field is gone too
        assert "--channel" not in command

    def test_project_can_add_fields_to_custom_tool(self):
        """Project can define its own tool with fields."""
        registry = load_registry(
            project_overrides={
                "my-tool": {
                    "install": {
                        "flags": "install",
                        "fields": {
                            "extras": {
                                "flag": "--extra",
                                "default": ["default-extra"],
                            }
                        },
                    }
                }
            }
        )
        step = {"my-tool": {"install": ["thing"]}}
        result = parse_step(step, registry)
        assert "--extra default-extra" in result["command"]
