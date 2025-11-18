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
            template={"base": "python:3-slim"},
        )
        assert config.project.name == name


def test_invalid_project_name():
    """Test that invalid project names are rejected."""
    invalid_names = ["my project", "my/project", "my.project", "my@project"]
    for name in invalid_names:
        with pytest.raises(ValidationError):
            ContainerMagicConfig(
                project={"name": name, "workspace": "workspace"},
                template={"base": "python:3-slim"},
            )


def test_default_values():
    """Test that default values are set correctly."""
    config = ContainerMagicConfig(
        project={"name": "test"}, template={"base": "python:3-slim"}
    )

    assert config.project.workspace == "workspace"
    assert config.runtime.backend == "auto"
    assert config.runtime.privileged is False
    assert config.development.mount_workspace is True
    assert config.development.shell == "/bin/bash"
    assert config.development.features == []
    assert config.production.user == "nonroot"


def test_config_with_features():
    """Test configuration with features enabled."""
    config = ContainerMagicConfig(
        project={"name": "test"},
        template={"base": "python:3-slim"},
        development={"features": ["display", "gpu", "audio"]},
    )

    assert "display" in config.development.features
    assert "gpu" in config.development.features
    assert "audio" in config.development.features


def test_config_with_packages():
    """Test configuration with package lists."""
    config = ContainerMagicConfig(
        project={"name": "test"},
        template={
            "base": "python:3-slim",
            "packages": {"apt": ["git", "curl"], "pip": ["numpy", "pandas"]},
        },
    )

    assert config.template.packages.apt == ["git", "curl"]
    assert config.template.packages.pip == ["numpy", "pandas"]
