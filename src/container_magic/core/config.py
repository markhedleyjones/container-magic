"""Configuration schema and validation for container-magic."""

import sys
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)


def _collect_extra_fields(model: BaseModel, path: str = "") -> List[str]:
    """Recursively collect paths to extra fields in a Pydantic model."""
    extras = []

    if hasattr(model, "model_extra") and model.model_extra:
        for key in model.model_extra:
            extras.append(f"{path}.{key}" if path else key)

    for field_name in type(model).model_fields:
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
        SystemExit: If config file not found
    """
    cm_yaml = path / "cm.yaml"

    if cm_yaml.exists():
        return cm_yaml

    print(
        "Error: No config file found (cm.yaml)",
        file=sys.stderr,
    )
    sys.exit(1)


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
                    f"assets[{i}]: URL must start with http:// or https://, got '{url}'"
                )
            filename = extract_filename_from_url(url)
            if not filename or filename == "asset":
                raise ValueError(
                    f"assets[{i}]: cannot derive filename from URL '{url}'. "
                    "Use explicit naming: {{ my-file.bin: {url} }}"
                )
        elif isinstance(entry, dict):
            if len(entry) != 1:
                raise ValueError(
                    f"assets[{i}]: named asset must be a single-key dict "
                    f"(filename: url), got {len(entry)} keys"
                )
            filename, url = next(iter(entry.items()))
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                raise ValueError(
                    f"assets[{i}]: URL must start with http:// or https://, got '{url}'"
                )
            if not filename:
                raise ValueError(f"assets[{i}]: filename must not be empty")
        else:
            raise ValueError(
                f"assets[{i}]: must be a URL string or a {{filename: url}} dict, "
                f"got {type(entry).__name__}"
            )

        if filename in seen_filenames:
            raise ValueError(
                f"assets[{i}]: duplicate filename '{filename}' "
                f"(first seen at index {seen_filenames[filename]})"
            )
        seen_filenames[filename] = i
        items.append(AssetItem(filename=filename, url=url))

    return items


class NamesConfig(BaseModel):
    """Naming configuration for the project."""

    model_config = ConfigDict(extra="allow")

    image: str = Field(description="Image name")
    workspace: str = Field(default="workspace", description="Workspace directory name")
    user: str = Field(description="Container username (or 'root' if no custom user)")

    @model_validator(mode="before")
    @classmethod
    def reject_renamed_fields(cls, data):
        """Reject fields that were renamed in v2 with migration messages."""
        if isinstance(data, dict) and "project" in data and "image" not in data:
            raise ValueError(
                "names.project has been renamed to names.image. "
                "Replace 'project' with 'image' in your names block."
            )
        return data


class RuntimeConfig(BaseModel):
    """Runtime configuration."""

    model_config = ConfigDict(extra="allow")

    privileged: Optional[bool] = Field(
        default=None, description="Run containers in privileged mode"
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
    shell: Optional[str] = Field(
        default=None,
        description="Interactive shell for cm run and run.sh when no command is given. "
        "Auto-detected from the base image if not specified.",
    )

    @model_validator(mode="before")
    @classmethod
    def reject_removed_fields(cls, data):
        """Reject fields that were removed in v2 with migration messages."""
        if not isinstance(data, dict):
            return data
        removed = {
            "network": "Use 'network_mode' instead",
            "backend": "Use root-level 'backend' instead of 'runtime.backend'",
        }
        for key, message in removed.items():
            if key in data:
                raise ValueError(f"runtime.{key} is not valid. {message}")
        return data

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

    def merge_with(self, stage_runtime: "RuntimeConfig") -> "RuntimeConfig":
        """Merge this (global) runtime with a stage-specific override.

        Scalars: stage value wins if set (not None / not default).
        Lists: stage values are appended to global values.
        """
        merged = self.model_copy(deep=True)

        # Scalar overrides - stage wins if explicitly set
        if stage_runtime.privileged is not None:
            merged.privileged = stage_runtime.privileged
        if stage_runtime.network_mode is not None:
            merged.network_mode = stage_runtime.network_mode
        if stage_runtime.ipc is not None:
            merged.ipc = stage_runtime.ipc
        if stage_runtime.shell is not None:
            merged.shell = stage_runtime.shell

        # List appends - stage values added to global
        merged.features = list(dict.fromkeys(merged.features + stage_runtime.features))
        merged.volumes = merged.volumes + stage_runtime.volumes
        merged.devices = merged.devices + stage_runtime.devices

        return merged


class StageConfig(BaseModel):
    """Build stage configuration."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    frm: str = Field(description="Base image or stage name to build from", alias="from")
    distro: Optional[str] = Field(
        default=None,
        description="Distribution family override (e.g. alpine, debian, ubuntu, fedora). "
        "Sets package manager, user creation style, and interactive shell. "
        "Inherited by child stages. package_manager and runtime.shell take precedence if also set.",
    )
    package_manager: Optional[Literal["apt", "apk", "dnf"]] = Field(
        default=None, description="Package manager (auto-detected if not specified)"
    )
    steps: Optional[List[Union[str, Dict[str, Any]]]] = Field(
        default=None,
        description="Ordered list of build steps: bare strings for keywords or Dockerfile passthrough, dicts for structured commands (run, copy, env, or command builder syntax)",
    )
    runtime: Optional[RuntimeConfig] = Field(
        default=None,
        description="Stage-specific runtime overrides. Scalars override the global runtime; "
        "lists (volumes, devices, features) are appended to the global values.",
    )

    @model_validator(mode="before")
    @classmethod
    def reject_removed_fields(cls, data):
        """Reject fields that moved in v3 with migration messages."""
        if not isinstance(data, dict):
            return data
        if "shell" in data:
            raise ValueError(
                "stages.<name>.shell has moved to runtime.shell or "
                "stages.<name>.runtime.shell. "
                "The shell field sets the interactive shell for cm run and run.sh."
            )
        return data


class MountSpec(BaseModel):
    """Mount specification for a command bind mount."""

    mode: Literal["ro", "rw"] = Field(
        description="Mount mode: ro (read-only) or rw (read-write)",
    )
    prefix: str = Field(
        default="",
        description="String prepended to container path in the command",
    )


class CustomCommand(BaseModel):
    """Custom command definition."""

    model_config = ConfigDict(extra="allow")

    command: str = Field(description="Base command to execute")
    description: Optional[str] = Field(default=None, description="Command description")
    env: Dict[str, str] = Field(
        default_factory=dict, description="Environment variables"
    )
    ports: List[str] = Field(
        default_factory=list,
        description="Ports to publish (host:container format)",
    )
    ipc: Optional[str] = Field(
        default=None,
        description="IPC namespace mode override (e.g. container:<name>)",
    )
    mounts: Dict[str, MountSpec] = Field(
        default_factory=dict,
        description="Named bind mounts (provided at runtime via name=/path syntax)",
    )

    @model_validator(mode="before")
    @classmethod
    def normalise_mounts(cls, data):
        """Convert shorthand mount values to MountSpec dicts."""
        if not isinstance(data, dict):
            return data
        mounts = data.get("mounts")
        if isinstance(mounts, dict):
            normalised = {}
            for name, spec in mounts.items():
                if isinstance(spec, str):
                    if spec not in ("ro", "rw"):
                        raise ValueError(
                            f"Mount '{name}' shorthand must be 'ro' or 'rw', got '{spec}'"
                        )
                    normalised[name] = {"mode": spec}
                else:
                    normalised[name] = spec
            data["mounts"] = normalised
        return data

    @model_validator(mode="before")
    @classmethod
    def reject_removed_fields(cls, data):
        """Reject fields removed in v3 with migration messages."""
        if not isinstance(data, dict):
            return data
        if "args" in data:
            raise ValueError(
                "Command 'args' have been replaced by 'mounts' in v3. "
                "See the v3 migration guide for details."
            )
        return data


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

    backend: Literal["auto", "docker", "podman"] = Field(
        default="auto", description="Container runtime to use"
    )
    names: NamesConfig
    assets: List[AssetItem] = Field(
        default_factory=list,
        description="Assets to download and cache (URLs or {filename: url} dicts)",
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

    def effective_runtime(self, stage_name: str) -> RuntimeConfig:
        """Resolve the effective runtime for a stage.

        Merges the global runtime with the stage-specific runtime override
        if one exists. Returns the global runtime unchanged if the stage
        has no override.
        """
        stage = self.stages.get(stage_name)
        if stage and stage.runtime:
            return self.runtime.merge_with(stage.runtime)
        return self.runtime

    @field_validator("assets", mode="before")
    @classmethod
    def parse_assets(cls, v):
        """Parse raw asset list into AssetItem objects."""
        if not v:
            return []
        return _parse_asset_items(v)

    @model_validator(mode="before")
    @classmethod
    def reject_removed_blocks(cls, data):
        """Reject removed config blocks with migration messages."""
        if not isinstance(data, dict):
            return data

        if "user" in data:
            raise ValueError(
                "The 'user' config block is no longer supported. "
                "Define the username in 'names.user' instead:\n"
                "  names:\n"
                "    image: my-project\n"
                "    user: appuser"
            )

        if "project" in data:
            raise ValueError(
                "The 'project' config block has been replaced by 'names'. "
                "Rename 'project' to 'names' and move 'name' to 'image':\n"
                "  names:\n"
                "    image: my-project\n"
                "    workspace: workspace\n"
                "    user: appuser"
            )

        if "auto_update" in data:
            raise ValueError(
                "'auto_update' is no longer used. Remove it from your cm.yaml."
            )

        return data

    @classmethod
    def from_yaml(cls, path: Path) -> "ContainerMagicConfig":
        """Load configuration from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            print("Error: cm.yaml must contain a YAML mapping", file=sys.stderr)
            sys.exit(1)

        try:
            config = cls(**data)
        except ValidationError as e:
            for error in e.errors():
                loc = (
                    ".".join(str(part) for part in error["loc"]) if error["loc"] else ""
                )
                msg = error["msg"]
                if msg.startswith("Value error, "):
                    msg = msg[len("Value error, ") :]
                if loc:
                    print(f"Error: {loc}: {msg}", file=sys.stderr)
                else:
                    print(f"Error: {msg}", file=sys.stderr)
            sys.exit(1)

        extra_fields = _collect_extra_fields(config)
        for field_path in extra_fields:
            print(
                f"Warning: Unknown config key '{field_path}' (ignored)", file=sys.stderr
            )

        if "build_script" in data:
            print(
                "Warning: 'build_script.default_target' only affects the standalone build.sh script. "
                "cm build accepts a target argument instead (e.g. cm build production).",
                file=sys.stderr,
            )

        return config

    def to_yaml(self, path: Path) -> None:
        """Save configuration to YAML file."""
        data = self.model_dump(exclude_none=True, by_alias=True)

        # Remove backend when it matches the default ("auto")
        if data.get("backend") == "auto":
            data.pop("backend", None)

        # Serialise assets back to YAML-friendly format
        raw_assets = data.get("assets", [])
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
            data["assets"] = yaml_assets
        else:
            data.pop("assets", None)

        # Omit default-valued blocks to keep scaffold minimal
        if data.get("commands") == {}:
            data.pop("commands", None)
        if data.get("command_registry") == {}:
            data.pop("command_registry", None)
        build_script = data.get("build_script", {})
        if build_script == {"default_target": "production"} or build_script == {}:
            data.pop("build_script", None)
        runtime = data.get("runtime", {})
        default_runtime = RuntimeConfig().model_dump(exclude_none=True)
        if runtime == {} or runtime == default_runtime:
            data.pop("runtime", None)

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

    @field_validator("names")
    @classmethod
    def validate_names_image(cls, v: NamesConfig) -> NamesConfig:
        """Validate image name doesn't contain invalid characters."""
        if not v.image.replace("-", "").replace("_", "").isalnum():
            raise ValueError(
                "Image name must contain only alphanumeric characters, hyphens, and underscores"
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

    @model_validator(mode="after")
    def validate_user_and_workspace_steps(self) -> "ContainerMagicConfig":
        """Validate user and workspace step consistency.

        User rules:
        - 'create: user' and 'become: user' require names.user != 'root'
        - 'create: root' is rejected at step parse time
        - 'create: <literal>' is allowed (secondary users)

        Workspace rules (single-token 'copy:' steps only):
        - 'copy: workspace' (matching names.workspace) is the primary mechanism
        - 'copy: <other>' without also copying the workspace is a warning
        - 'copy: <other>' alongside the workspace copy is an info
        """
        has_workspace_copy = False
        literal_copies = []

        for stage in self.stages.values():
            if not stage.steps:
                continue
            for step in stage.steps:
                if not isinstance(step, dict) or len(step) != 1:
                    continue
                key = next(iter(step))
                value = step[key]
                if key == "create" and value == "user":
                    if self.names.user == "root":
                        raise ValueError(
                            "'create: user' cannot be used when names.user is 'root' "
                            "(root always exists). Set names.user to a non-root username."
                        )
                elif key == "create" and isinstance(value, str) and value != "root":
                    pass
                if key == "become" and value == "user" and self.names.user == "root":
                    raise ValueError(
                        "'become: user' is redundant when names.user is 'root' "
                        "(containers run as root by default). Remove the step."
                    )
                if key == "copy" and isinstance(value, str):
                    # Single-token copies are workspace-style (copied into home)
                    if " " not in value.strip():
                        if value.strip() == self.names.workspace:
                            has_workspace_copy = True
                        else:
                            literal_copies.append(value.strip())

        for name in literal_copies:
            if has_workspace_copy:
                print(
                    f"Info: 'copy: {name}' copies a directory that is not the "
                    f"defined workspace ('{self.names.workspace}')",
                    file=sys.stderr,
                )
            else:
                print(
                    f"Warning: 'copy: {name}' copies a directory that is not the "
                    f"defined workspace ('{self.names.workspace}'). "
                    f"Use 'copy: {self.names.workspace}' to copy the workspace, "
                    f"or update names.workspace if '{name}' is your workspace.",
                    file=sys.stderr,
                )

        return self
