"""Configuration schema and validation for container-magic."""

import sys
from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


def find_config_file(path: Path) -> Path:
    """
    Find the config file to use.

    Priority: cm.yaml > container-magic.yaml

    Raises:
        SystemExit: If both files exist or neither exists
    """
    cm_yaml = path / "cm.yaml"
    container_magic_yaml = path / "container-magic.yaml"

    if cm_yaml.exists() and container_magic_yaml.exists():
        print("Error: Both cm.yaml and container-magic.yaml found.", file=sys.stderr)
        print("Please delete one to avoid confusion.", file=sys.stderr)
        sys.exit(1)

    if cm_yaml.exists():
        return cm_yaml
    elif container_magic_yaml.exists():
        return container_magic_yaml
    else:
        print(
            "Error: No config file found (cm.yaml or container-magic.yaml)",
            file=sys.stderr,
        )
        sys.exit(1)


class UserConfig(BaseModel):
    """User configuration."""

    name: str = Field(description="User name")
    uid: int = Field(default=1000, description="User ID")
    gid: int = Field(default=1000, description="Group ID")
    home: Optional[str] = Field(
        default=None, description="Home directory (defaults to /home/${name})"
    )


class ProjectConfig(BaseModel):
    """Project configuration."""

    name: str = Field(description="Project name")
    workspace: str = Field(default="workspace", description="Workspace directory name")
    auto_update: bool = Field(
        default=False,
        description="Automatically regenerate files when config changes",
    )
    user: Optional[UserConfig] = Field(
        default=None, description="User for both development and production"
    )
    production_user: Optional[UserConfig] = Field(
        default=None,
        description="User for production (development uses host user)",
    )
    development_user: Optional[UserConfig] = Field(
        default=None, description="User for development (production uses root)"
    )


class RuntimeConfig(BaseModel):
    """Runtime configuration."""

    backend: Literal["auto", "docker", "podman"] = Field(
        default="auto", description="Container runtime to use"
    )
    privileged: bool = Field(
        default=False, description="Run containers in privileged mode"
    )
    features: list[Literal["display", "gpu", "audio", "aws_credentials"]] = Field(
        default_factory=list, description="Features to enable in containers"
    )


class PackagesConfig(BaseModel):
    """Package installation configuration."""

    apt: list[str] = Field(default_factory=list, description="APT packages to install")
    pip: list[str] = Field(
        default_factory=list, description="Python pip packages to install"
    )


class CachedAsset(BaseModel):
    """Cached asset configuration."""

    url: str = Field(description="URL to download asset from")
    dest: str = Field(description="Destination path in container")


class StageConfig(BaseModel):
    """Build stage configuration."""

    frm: str = Field(description="Base image or stage name to build from", alias="from")
    packages: PackagesConfig = Field(default_factory=PackagesConfig)
    package_manager: Optional[Literal["apt", "apk", "dnf"]] = Field(
        default=None, description="Package manager (auto-detected if not specified)"
    )
    shell: Optional[str] = Field(
        default=None, description="Default shell (auto-detected if not specified)"
    )
    env: dict[str, str] = Field(
        default_factory=dict, description="Environment variables to set in Dockerfile"
    )
    cached_assets: list[CachedAsset] = Field(
        default_factory=list,
        description="Assets to download and cache on host, then copy into image",
    )
    steps: Optional[list[str]] = Field(
        default=None,
        description="Ordered list of build steps with special keywords: install_system_packages, install_pip_packages, create_user, switch_user, switch_root, copy_cached_assets",
        alias="build_steps",  # Support old name for backwards compatibility
    )

    class Config:
        populate_by_name = True


class CommandArgument(BaseModel):
    """Command argument definition."""

    type: Literal["file", "directory", "string", "int", "float"] = Field(
        description="Argument type"
    )
    mount_as: Optional[str] = Field(
        default=None, description="Container path to mount file/directory arguments"
    )
    readonly: bool = Field(
        default=True, description="Mount as read-only (for file/directory types)"
    )
    default: Optional[Any] = Field(default=None, description="Default value")
    description: Optional[str] = Field(default=None, description="Argument description")


class CustomCommand(BaseModel):
    """Custom command definition."""

    command: str = Field(description="Command template with {arg_name} placeholders")
    args: dict[str, CommandArgument] = Field(
        default_factory=dict, description="Command arguments"
    )
    description: Optional[str] = Field(default=None, description="Command description")
    env: dict[str, str] = Field(
        default_factory=dict, description="Environment variables"
    )
    allow_extra_args: bool = Field(
        default=False,
        description="Allow passing extra arguments after defined args (appended to command)",
    )


class ContainerMagicConfig(BaseModel):
    """Complete container-magic configuration."""

    project: ProjectConfig
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    stages: dict[str, StageConfig]
    commands: dict[str, CustomCommand] = Field(
        default_factory=dict, description="Custom command definitions"
    )

    @classmethod
    def from_yaml(cls, path: Path) -> "ContainerMagicConfig":
        """Load configuration from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def to_yaml(self, path: Path, compact: bool = True) -> None:
        """Save configuration to YAML file.

        Args:
            path: Path to save YAML file
            compact: If False, include helpful comments (default: True)
        """
        data = self.model_dump(exclude_none=True, by_alias=True)

        # Custom YAML dumper that adds blank lines between top-level sections
        class BlankLineDumper(yaml.SafeDumper):
            def increase_indent(self, flow=False, indentless=False):
                """Override to make list items not indented (yamlfmt style)."""
                return super().increase_indent(flow, False)

        def write_blank_line(dumper, data):
            """Add blank line before top-level mappings."""
            return dumper.represent_dict(data)

        BlankLineDumper.add_representer(dict, write_blank_line)

        # Dump YAML with yamlfmt-compatible formatting
        output = yaml.dump(
            data,
            Dumper=BlankLineDumper,
            default_flow_style=False,
            sort_keys=False,
            width=float("inf"),  # Prevent line wrapping
            indent=2,  # yamlfmt standard
        )

        # Add blank lines between top-level sections
        lines = output.split("\n")
        formatted_lines = []
        for i, line in enumerate(lines):
            # Add blank line before top-level keys (no leading whitespace)
            if line and not line[0].isspace() and i > 0 and formatted_lines:
                formatted_lines.append("")
            formatted_lines.append(line)

        output = "\n".join(formatted_lines)

        # Add comments if not compact
        if not compact:
            output = self._add_comments(output)
        else:
            # Add minimal header for compact config
            compact_header = "# https://github.com/markhedleyjones/container-magic\n"
            output = compact_header + output

        with open(path, "w") as f:
            f.write(output)

        # Format with yamlfmt if available
        import shutil
        import subprocess

        if shutil.which("yamlfmt"):
            subprocess.run(
                ["yamlfmt", "-formatter", "retain_line_breaks=true", str(path)],
                capture_output=True,
            )

    def _add_comments(self, yaml_content: str) -> str:
        """Add helpful comments to YAML content."""
        header = """# container-magic.yaml
# Configuration file for container-magic - a tool for containerised development environments
#
# Repository: https://github.com/markhedleyjones/container-magic
# Install: pip install container-magic
# For a more compact config without comments, use: cm init --compact

"""

        # Add section comments
        commented = header + yaml_content

        # Add comments above keys (only first occurrence)
        replacements = [
            ("project:", "# Project configuration\nproject:"),
            ("  name:", "  # Project name (used for Docker image tagging)\n  name:"),
            (
                "  workspace:",
                "  # Directory containing your code (mounted into container)\n  workspace:",
            ),
            (
                "  auto_update:",
                "  # Automatically regenerate Dockerfile and Justfile when this file changes\n  auto_update:",
            ),
            (
                "  production_user:",
                "  # User to create in production image\n  production_user:",
            ),
            ("runtime:", "# Container runtime configuration\nruntime:"),
            (
                "  backend:",
                "  # Container runtime: auto, docker, or podman\n  backend:",
            ),
            (
                "  privileged:",
                "  # Run containers in privileged mode (for hardware access)\n  privileged:",
            ),
            (
                "  features:",
                "  # Features to enable: display, gpu, audio, aws_credentials\n  features:",
            ),
            ("stages:", "# Build stages - each stage builds on the previous\nstages:"),
            ("  base:", "  # Base stage - foundation for all other stages\n  base:"),
            (
                "    from:",
                "    # Base image to build from (any Docker image)\n    from:",
            ),
            ("    packages:", "    # Packages to install\n    packages:"),
            (
                "      apt:",
                "      # System packages (apt/apk/dnf depending on base image)\n      apt:",
            ),
            ("      pip:", "      # Python packages\n      pip:"),
            ("    env:", "    # Environment variables\n    env:"),
            (
                "    cached_assets:",
                "    # Large files to download and cache (e.g. model weights)\n    cached_assets:",
            ),
            (
                "  development:",
                "  # Development stage - used when running locally\n  development:",
            ),
            (
                "    steps:",
                "    # Build steps: install_system_packages, install_pip_packages, create_user, switch_user, copy_cached_assets\n    steps:",
            ),
            (
                "  production:",
                "  # Production stage - final deployable image\n  production:",
            ),
            (
                "commands:",
                "# Custom commands - define your own container commands\ncommands:",
            ),
        ]

        for old, new in replacements:
            commented = commented.replace(old, new, 1)  # Only replace first occurrence

        return commented

    @field_validator("project")
    @classmethod
    def validate_project_name(cls, v: ProjectConfig) -> ProjectConfig:
        """Validate project name doesn't contain invalid characters."""
        if not v.name.replace("-", "").replace("_", "").isalnum():
            raise ValueError(
                "Project name must contain only alphanumeric characters, hyphens, and underscores"
            )
        return v

    @model_validator(mode="after")
    def validate_user_config(self) -> "ContainerMagicConfig":
        """Validate that only one user config variant is specified."""
        user_configs = [
            self.project.user is not None,
            self.project.production_user is not None,
            self.project.development_user is not None,
        ]
        if sum(user_configs) > 1:
            raise ValueError(
                "Can only specify one of: user, production_user, or development_user"
            )
        return self

    @model_validator(mode="after")
    def validate_required_stages(self) -> "ContainerMagicConfig":
        """Validate that development and production stages exist."""
        if "development" not in self.stages:
            raise ValueError("stages.development is required")
        if "production" not in self.stages:
            raise ValueError("stages.production is required")
        return self
