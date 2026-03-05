"""Configuration schema and validation for container-magic."""

import sys
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _collect_extra_fields(model: BaseModel, path: str = "") -> List[str]:
    """Recursively collect paths to extra fields in a Pydantic model."""
    extras = []

    if hasattr(model, "model_extra") and model.model_extra:
        for key in model.model_extra:
            extras.append(f"{path}.{key}" if path else key)

    for field_name in model.model_fields:
        value = getattr(model, field_name)
        field_path = f"{path}.{field_name}" if path else field_name

        if isinstance(value, BaseModel):
            extras.extend(_collect_extra_fields(value, field_path))
        elif isinstance(value, dict):
            for k, v in value.items():
                if isinstance(v, BaseModel):
                    extras.extend(_collect_extra_fields(v, f"{field_path}.{k}"))

    return extras


def find_config_file(path: Path) -> Path:
    """
    Find the config file to use.

    Raises:
        SystemExit: If config file not found or old name is used
    """
    cm_yaml = path / "cm.yaml"
    container_magic_yaml = path / "container-magic.yaml"

    if cm_yaml.exists():
        return cm_yaml
    elif container_magic_yaml.exists():
        print(
            "Error: Rename container-magic.yaml to cm.yaml",
            file=sys.stderr,
        )
        sys.exit(1)
    else:
        print(
            "Error: No config file found (cm.yaml)",
            file=sys.stderr,
        )
        sys.exit(1)


class UserTargetConfig(BaseModel):
    """User configuration for a specific target (development, production, etc.)."""

    model_config = ConfigDict(extra="allow")

    name: Optional[str] = Field(default=None, description="User name")
    uid: Optional[int] = Field(default=None, description="User ID")
    gid: Optional[int] = Field(default=None, description="Group ID")
    home: Optional[str] = Field(
        default=None, description="Home directory (defaults to /home/${name})"
    )
    host: Optional[bool] = Field(
        default=None, description="Use host user (capture actual UID/GID at build time)"
    )

    @model_validator(mode="after")
    def validate_host_field(self) -> "UserTargetConfig":
        """Validate that host is true or omitted, never false."""
        if self.host is False:
            raise ValueError(
                "host must be true or omitted. "
                "If false, just omit the host field and specify name, uid, gid instead"
            )
        return self

    @model_validator(mode="after")
    def validate_host_exclusive(self) -> "UserTargetConfig":
        """Validate that host: true is not combined with name/uid/gid."""
        if self.host is True:
            if self.name is not None or self.uid is not None or self.gid is not None:
                raise ValueError(
                    "host: true cannot be combined with name, uid, or gid. "
                    "host: true means use the actual host user, so other fields are ignored"
                )
        return self

    @model_validator(mode="after")
    def validate_name_required(self) -> "UserTargetConfig":
        """Validate that name is provided when host is not true."""
        if self.host is not True and self.name is None:
            if self.uid is not None or self.gid is not None or self.home is not None:
                raise ValueError(
                    "user name is required when uid, gid, or home is specified. "
                    "Add name: <username> to your user configuration"
                )
        return self


class UserConfig(BaseModel):
    """Top-level user configuration for different targets."""

    model_config = ConfigDict(extra="allow")

    development: Optional[UserTargetConfig] = Field(
        default=None, description="User configuration for development target"
    )
    production: Optional[UserTargetConfig] = Field(
        default=None, description="User configuration for production target"
    )


class AssetItem(BaseModel):
    """Normalised asset entry (filename + URL)."""

    filename: str
    url: str


def _parse_asset_items(raw_assets: list) -> List[AssetItem]:
    """Parse raw asset list into normalised AssetItem objects.

    Each item is either:
    - A bare URL string (filename auto-derived from URL path)
    - A single-key dict where the key is the filename and the value is the URL
    """
    from container_magic.core.cache import extract_filename_from_url

    items: List[AssetItem] = []
    seen_filenames: Dict[str, int] = {}

    for i, entry in enumerate(raw_assets):
        if isinstance(entry, str):
            url = entry
            if not url.startswith(("http://", "https://")):
                raise ValueError(
                    f"project.assets[{i}]: URL must start with http:// or https://, got '{url}'"
                )
            filename = extract_filename_from_url(url)
            if not filename or filename == "asset":
                raise ValueError(
                    f"project.assets[{i}]: cannot derive filename from URL '{url}'. "
                    "Use explicit naming: {{ my-file.bin: {url} }}"
                )
        elif isinstance(entry, dict):
            if len(entry) != 1:
                raise ValueError(
                    f"project.assets[{i}]: named asset must be a single-key dict "
                    f"(filename: url), got {len(entry)} keys"
                )
            filename, url = next(iter(entry.items()))
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                raise ValueError(
                    f"project.assets[{i}]: URL must start with http:// or https://, got '{url}'"
                )
            if not filename:
                raise ValueError(f"project.assets[{i}]: filename must not be empty")
        else:
            raise ValueError(
                f"project.assets[{i}]: must be a URL string or a {{filename: url}} dict, "
                f"got {type(entry).__name__}"
            )

        if filename in seen_filenames:
            raise ValueError(
                f"project.assets[{i}]: duplicate filename '{filename}' "
                f"(first seen at index {seen_filenames[filename]})"
            )
        seen_filenames[filename] = i
        items.append(AssetItem(filename=filename, url=url))

    return items


class ProjectConfig(BaseModel):
    """Project configuration."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(description="Project name")
    workspace: str = Field(default="workspace", description="Workspace directory name")
    auto_update: bool = Field(
        default=True,
        description="Automatically regenerate files when config changes",
    )
    assets: List[AssetItem] = Field(
        default_factory=list,
        description="Assets to download and cache (URLs or {filename: url} dicts)",
    )

    @field_validator("assets", mode="before")
    @classmethod
    def parse_assets(cls, v):
        """Parse raw asset list into AssetItem objects."""
        if not v:
            return []
        return _parse_asset_items(v)


class RuntimeConfig(BaseModel):
    """Runtime configuration."""

    model_config = ConfigDict(extra="allow")

    backend: Literal["auto", "docker", "podman"] = Field(
        default="auto", description="Container runtime to use"
    )
    privileged: bool = Field(
        default=False, description="Run containers in privileged mode"
    )
    network_mode: Optional[Literal["host", "bridge", "none"]] = Field(
        default=None,
        description="Container network mode (host, bridge, none)",
    )
    features: List[Literal["display", "gpu", "audio", "aws_credentials"]] = Field(
        default_factory=list, description="Features to enable in containers"
    )
    volumes: List[str] = Field(
        default_factory=list,
        description="Additional bind mounts (host:container[:options])",
    )
    devices: List[str] = Field(
        default_factory=list,
        description="Host devices to pass through (host_path:container_path[:permissions])",
    )
    ipc: Optional[str] = Field(
        default=None,
        description="IPC namespace mode (e.g. shareable, container:<name>, host, private)",
    )

    @field_validator("volumes")
    @classmethod
    def validate_volume_format(cls, v):
        """Validate volume strings have at least host:container."""
        for volume in v:
            parts = volume.split(":")
            if len(parts) < 2 or not parts[0] or not parts[1]:
                raise ValueError(
                    f"Invalid volume format '{volume}': must be host:container[:options]"
                )
        return v

    @field_validator("devices")
    @classmethod
    def validate_device_format(cls, v):
        """Validate device strings are non-empty."""
        for device in v:
            if not device.strip():
                raise ValueError("Device path must not be empty")
        return v


class PackagesConfig(BaseModel):
    """Package installation configuration."""

    model_config = ConfigDict(extra="allow")

    apt: Optional[List[str]] = Field(
        default=None, description="APT packages to install"
    )
    apk: Optional[List[str]] = Field(
        default=None, description="APK packages to install"
    )
    dnf: Optional[List[str]] = Field(
        default=None, description="DNF packages to install"
    )
    pip: List[str] = Field(
        default_factory=list, description="Python pip packages to install"
    )


class StageConfig(BaseModel):
    """Build stage configuration."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    frm: str = Field(description="Base image or stage name to build from", alias="from")
    packages: PackagesConfig = Field(default_factory=PackagesConfig)
    package_manager: Optional[Literal["apt", "apk", "dnf"]] = Field(
        default=None, description="Package manager (auto-detected if not specified)"
    )
    shell: Optional[str] = Field(
        default=None, description="Default shell (auto-detected if not specified)"
    )
    env: Dict[str, str] = Field(
        default_factory=dict, description="Environment variables to set in Dockerfile"
    )
    steps: Optional[List[Union[str, Dict[str, Any]]]] = Field(
        default=None,
        description="Ordered list of build steps: bare strings for keywords or Dockerfile passthrough, dicts for structured commands (run, copy, env, or command builder syntax)",
    )


class CommandArgument(BaseModel):
    """Command argument definition."""

    model_config = ConfigDict(extra="allow")

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

    model_config = ConfigDict(extra="allow")

    command: str = Field(description="Command template with {arg_name} placeholders")
    args: Dict[str, CommandArgument] = Field(
        default_factory=dict, description="Command arguments"
    )
    description: Optional[str] = Field(default=None, description="Command description")
    env: Dict[str, str] = Field(
        default_factory=dict, description="Environment variables"
    )
    ports: List[str] = Field(
        default_factory=list,
        description="Ports to publish (host:container format)",
    )
    standalone: bool = Field(
        default=False,
        description="Generate standalone script for this command",
    )
    ipc: Optional[str] = Field(
        default=None,
        description="IPC namespace mode override (e.g. container:<name>)",
    )


class BuildScriptConfig(BaseModel):
    """Build script configuration."""

    model_config = ConfigDict(extra="allow")

    default_target: str = Field(
        default="production",
        description="Default stage to build when running build.sh without arguments",
    )


class ContainerMagicConfig(BaseModel):
    """Complete container-magic configuration."""

    model_config = ConfigDict(extra="allow")

    project: ProjectConfig
    user: Optional[UserConfig] = Field(
        default=None,
        description="User configuration for development and production targets",
    )
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    stages: Dict[str, StageConfig]
    commands: Dict[str, CustomCommand] = Field(
        default_factory=dict, description="Custom command definitions"
    )
    command_registry: Dict[str, Any] = Field(
        default_factory=dict,
        description="Per-project command registry overrides for structured step syntax",
    )
    build_script: BuildScriptConfig = Field(default_factory=BuildScriptConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> "ContainerMagicConfig":
        """Load configuration from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        config = cls(**data)

        extra_fields = _collect_extra_fields(config)
        for field_path in extra_fields:
            print(
                f"Warning: Unknown config key '{field_path}' (ignored)", file=sys.stderr
            )

        return config

    def to_yaml(self, path: Path) -> None:
        """Save configuration to YAML file."""
        data = self.model_dump(exclude_none=True, by_alias=True)

        # Remove auto_update from output when it matches the default (True)
        # It's noise in the config — users only need it when opting out
        if data.get("project", {}).get("auto_update") is True:
            data["project"].pop("auto_update", None)

        # Serialise assets back to YAML-friendly format (list of URLs / {name: url} dicts)
        raw_assets = data.get("project", {}).get("assets", [])
        if raw_assets:
            from container_magic.core.cache import extract_filename_from_url

            yaml_assets = []
            for item in raw_assets:
                url = item["url"]
                filename = item["filename"]
                auto_name = extract_filename_from_url(url)
                if filename == auto_name:
                    yaml_assets.append(url)
                else:
                    yaml_assets.append({filename: url})
            data["project"]["assets"] = yaml_assets
        else:
            data["project"].pop("assets", None)

        # Strip empty system package lists only when a populated one exists,
        # so configs with e.g. apt: [curl] don't also show apk: [] and dnf: [].
        # When all are empty (e.g. scaffolds), keep them to hint which field to use.
        for stage_data in data.get("stages", {}).values():
            packages = stage_data.get("packages", {})
            sys_pkg_fields = ("apt", "apk", "dnf")
            has_populated = any(packages.get(f) for f in sys_pkg_fields)
            if has_populated:
                for pkg_mgr in sys_pkg_fields:
                    if pkg_mgr in packages and packages[pkg_mgr] == []:
                        del packages[pkg_mgr]

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

        # Add header
        header = "# https://github.com/markhedleyjones/container-magic\n"
        output = header + output

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
    def validate_required_stages(self) -> "ContainerMagicConfig":
        """Validate that development and production stages exist."""
        if "development" not in self.stages:
            raise ValueError("stages.development is required")
        if "production" not in self.stages:
            raise ValueError("stages.production is required")
        return self

    @model_validator(mode="after")
    def validate_build_script_target(self) -> "ContainerMagicConfig":
        """Validate that build_script.default_target exists in stages."""
        if self.build_script.default_target not in self.stages:
            raise ValueError(
                f"build_script.default_target '{self.build_script.default_target}' "
                f"does not exist in stages. Available stages: {', '.join(self.stages.keys())}"
            )
        return self
