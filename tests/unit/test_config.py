"""Tests for configuration schema and validation."""

import pytest
from pydantic import ValidationError

from container_magic.core.config import ContainerMagicConfig


def test_valid_project_name():
    """Test that valid project names are accepted."""
    valid_names = ["my-project", "my_project", "myproject", "my-project-123"]
    for name in valid_names:
        config = ContainerMagicConfig(
            project={"name": name, "workspace": "workspace"},
            stages={
                "base": {"from": "python:3-slim"},
                "development": {"from": "base"},
                "production": {"from": "base"},
            },
        )
        assert config.project.name == name


def test_invalid_project_name():
    """Test that invalid project names are rejected."""
    invalid_names = ["my project", "my/project", "my.project", "my@project"]
    for name in invalid_names:
        with pytest.raises(ValidationError):
            ContainerMagicConfig(
                project={"name": name, "workspace": "workspace"},
                stages={
                    "base": {"from": "python:3-slim"},
                    "development": {"from": "base"},
                    "production": {"from": "base"},
                },
            )


def test_default_values():
    """Test that default values are set correctly."""
    config = ContainerMagicConfig(
        project={"name": "test"},
        stages={
            "base": {"from": "python:3-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
    )

    assert config.project.workspace == "workspace"
    assert config.runtime.backend == "auto"
    assert config.runtime.privileged is False
    assert config.runtime.features == []
    assert config.runtime.volumes == []
    assert config.runtime.devices == []
    assert config.runtime.network_mode is None


def test_config_with_features():
    """Test configuration with features enabled."""
    config = ContainerMagicConfig(
        project={"name": "test"},
        runtime={"features": ["display", "gpu", "audio"]},
        stages={
            "base": {"from": "python:3-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
    )

    assert config.runtime.features == ["display", "gpu", "audio"]


def test_config_with_volumes():
    """Test configuration with volumes."""
    config = ContainerMagicConfig(
        project={"name": "test"},
        runtime={"volumes": ["/tmp/data:/data:ro", "/var/log:/logs"]},
        stages={
            "base": {"from": "python:3-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
    )

    assert config.runtime.volumes == ["/tmp/data:/data:ro", "/var/log:/logs"]


def test_config_with_devices():
    """Test configuration with devices."""
    config = ContainerMagicConfig(
        project={"name": "test"},
        runtime={"devices": ["/dev/ttyUSB0", "/dev/video0:/dev/video0:rw"]},
        stages={
            "base": {"from": "python:3-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
    )

    assert config.runtime.devices == ["/dev/ttyUSB0", "/dev/video0:/dev/video0:rw"]


def test_invalid_volume_format():
    """Test that invalid volume strings are rejected."""
    with pytest.raises(ValidationError, match="Invalid volume format"):
        ContainerMagicConfig(
            project={"name": "test"},
            runtime={"volumes": ["no-colon"]},
            stages={
                "base": {"from": "python:3-slim"},
                "development": {"from": "base"},
                "production": {"from": "base"},
            },
        )


def test_invalid_volume_empty_parts():
    """Test that volume strings with empty host or container are rejected."""
    with pytest.raises(ValidationError, match="Invalid volume format"):
        ContainerMagicConfig(
            project={"name": "test"},
            runtime={"volumes": [":/container"]},
            stages={
                "base": {"from": "python:3-slim"},
                "development": {"from": "base"},
                "production": {"from": "base"},
            },
        )


def test_removed_network_field_raises():
    """Test that runtime.network is rejected with a migration message."""
    with pytest.raises(ValidationError, match="network_mode"):
        ContainerMagicConfig(
            project={"name": "test"},
            runtime={"network": "host"},
            stages={
                "base": {"from": "python:3-slim"},
                "development": {"from": "base"},
                "production": {"from": "base"},
            },
        )


def test_build_script_custom_default_target():
    """Test that build_script.default_target can be customised."""
    config = ContainerMagicConfig(
        project={"name": "test"},
        stages={
            "base": {"from": "python:3-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
            "testing": {"from": "base"},
        },
        build_script={"default_target": "testing"},
    )

    assert config.build_script.default_target == "testing"


def test_build_script_invalid_default_target():
    """Test that build_script.default_target must exist in stages."""
    with pytest.raises(ValidationError) as exc_info:
        ContainerMagicConfig(
            project={"name": "test"},
            stages={
                "base": {"from": "python:3-slim"},
                "development": {"from": "base"},
                "production": {"from": "base"},
            },
            build_script={"default_target": "nonexistent"},
        )

    assert "does not exist in stages" in str(exc_info.value)
