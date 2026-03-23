"""Unit tests for mount configuration schema."""

from container_magic.core.config import ContainerMagicConfig
import pytest


def _make_config_with_command(**command_overrides):
    """Create a config with a custom command."""
    command_data = {"command": "test-cmd"}
    command_data.update(command_overrides)
    return ContainerMagicConfig(
        names={"image": "test-project", "user": "nonroot"},
        stages={
            "base": {"from": "debian:bookworm-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
        commands={"test": command_data},
    )


class TestMountShorthand:
    def test_ro_shorthand(self):
        config = _make_config_with_command(mounts={"bag": "ro"})
        mount = config.commands["test"].mounts["bag"]
        assert mount.mode == "ro"
        assert mount.prefix == ""

    def test_rw_shorthand(self):
        config = _make_config_with_command(mounts={"results": "rw"})
        mount = config.commands["test"].mounts["results"]
        assert mount.mode == "rw"
        assert mount.prefix == ""

    def test_invalid_shorthand_rejected(self):
        with pytest.raises(Exception):
            _make_config_with_command(mounts={"bag": "readonly"})


class TestMountFullForm:
    def test_full_form_with_prefix(self):
        config = _make_config_with_command(
            mounts={"bag": {"mode": "ro", "prefix": "--bag "}}
        )
        mount = config.commands["test"].mounts["bag"]
        assert mount.mode == "ro"
        assert mount.prefix == "--bag "

    def test_full_form_mode_required(self):
        with pytest.raises(Exception):
            _make_config_with_command(mounts={"bag": {"prefix": "--bag "}})

    def test_mixed_forms(self):
        config = _make_config_with_command(
            mounts={
                "bag": "ro",
                "results": {"mode": "rw", "prefix": "--output "},
            }
        )
        assert config.commands["test"].mounts["bag"].mode == "ro"
        assert config.commands["test"].mounts["results"].mode == "rw"
        assert config.commands["test"].mounts["results"].prefix == "--output "


class TestMountModeValidation:
    def test_ro_valid(self):
        config = _make_config_with_command(mounts={"x": "ro"})
        assert config.commands["test"].mounts["x"].mode == "ro"

    def test_rw_valid(self):
        config = _make_config_with_command(mounts={"x": "rw"})
        assert config.commands["test"].mounts["x"].mode == "rw"

    def test_invalid_mode_rejected(self):
        with pytest.raises(Exception):
            _make_config_with_command(mounts={"x": "rx"})
