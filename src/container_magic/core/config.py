"""Configuration schema and validation for container-magic."""

from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class ProjectConfig(BaseModel):
    """Project configuration."""

    name: str = Field(description="Project name")
    workspace: str = Field(default="workspace", description="Workspace directory name")


class RuntimeConfig(BaseModel):
    """Runtime configuration."""

    backend: Literal["auto", "docker", "podman"] = Field(
        default="auto", description="Container runtime to use"
    )
    privileged: bool = Field(
        default=False, description="Run containers in privileged mode"
    )


class PackagesConfig(BaseModel):
    """Package installation configuration."""

    apt: list[str] = Field(default_factory=list, description="APT packages to install")
    pip: list[str] = Field(
        default_factory=list, description="Python pip packages to install"
    )


class TemplateConfig(BaseModel):
    """Template configuration."""

    base: str = Field(description="Base Docker image")
    packages: PackagesConfig = Field(default_factory=PackagesConfig)
    package_manager: Optional[Literal["apt", "apk", "dnf"]] = Field(
        default=None, description="Package manager (auto-detected if not specified)"
    )
    shell: Optional[str] = Field(
        default=None, description="Default shell (auto-detected if not specified)"
    )


class DevelopmentConfig(BaseModel):
    """Development environment configuration."""

    mount_workspace: bool = Field(
        default=True, description="Mount workspace directory into container"
    )
    shell: Optional[str] = Field(
        default=None,
        description="Shell to use in container (auto-detected if not specified)",
    )
    features: list[Literal["display", "gpu", "audio", "aws_credentials"]] = Field(
        default_factory=list, description="Features to enable"
    )


class ProductionConfig(BaseModel):
    """Production environment configuration."""

    user: str = Field(default="nonroot", description="User to run container as")
    entrypoint: Optional[str] = Field(default=None, description="Container entrypoint")


class ContainerMagicConfig(BaseModel):
    """Complete container-magic configuration."""

    project: ProjectConfig
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    template: TemplateConfig
    development: DevelopmentConfig = Field(default_factory=DevelopmentConfig)
    production: ProductionConfig = Field(default_factory=ProductionConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> "ContainerMagicConfig":
        """Load configuration from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def to_yaml(self, path: Path) -> None:
        """Save configuration to YAML file."""
        data = self.model_dump(exclude_none=True)
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    @field_validator("project")
    @classmethod
    def validate_project_name(cls, v: ProjectConfig) -> ProjectConfig:
        """Validate project name doesn't contain invalid characters."""
        if not v.name.replace("-", "").replace("_", "").isalnum():
            raise ValueError(
                "Project name must contain only alphanumeric characters, hyphens, and underscores"
            )
        return v
