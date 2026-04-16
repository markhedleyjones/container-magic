"""Command registry for structured step syntax.

Loads built-in command definitions from YAML files and merges with
per-project overrides. Provides lookup by command path (e.g. "apt-get.install")
to retrieve flags and cleanup commands.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


_REGISTRY_DIR = Path(__file__).parent.parent / "registry"


class FieldSpec:
    """A step field that maps to one or more CLI flags.

    type 'repeated_flag': each value in the user's list (or default) becomes
    a '<flag> <value>' pair, in order. E.g. conda's channels.
    """

    def __init__(
        self,
        flag: str,
        default: Optional[List[Any]] = None,
        field_type: str = "repeated_flag",
    ):
        self.flag = flag
        self.default = list(default) if default else []
        self.type = field_type

    def __repr__(self):
        return (
            f"FieldSpec(flag={self.flag!r}, default={self.default!r}, "
            f"type={self.type!r})"
        )


class RegistryEntry:
    """A single registry entry with optional setup, flags, cleanup, and fields.

    installs_python_packages signals to the Dockerfile generator that this
    subcommand puts .py files into site-packages, so bytecode compilation
    should run afterwards.
    """

    def __init__(
        self,
        setup: str = "",
        flags: str = "",
        cleanup: str = "",
        fields: Optional[Dict[str, FieldSpec]] = None,
        installs_python_packages: bool = False,
    ):
        self.setup = setup
        self.flags = flags
        self.cleanup = cleanup
        self.fields = fields or {}
        self.installs_python_packages = installs_python_packages

    def __repr__(self):
        return (
            f"RegistryEntry(setup={self.setup!r}, flags={self.flags!r}, "
            f"cleanup={self.cleanup!r}, fields={self.fields!r}, "
            f"installs_python_packages={self.installs_python_packages!r})"
        )


def _parse_fields(fields_data: Any) -> Dict[str, FieldSpec]:
    """Convert a registry YAML 'fields' block into a FieldSpec dict."""
    if not isinstance(fields_data, dict):
        return {}
    result: Dict[str, FieldSpec] = {}
    for field_name, spec in fields_data.items():
        if not isinstance(spec, dict):
            continue
        flag = spec.get("flag")
        if not flag:
            continue
        result[field_name] = FieldSpec(
            flag=flag,
            default=spec.get("default"),
            field_type=spec.get("type", "repeated_flag"),
        )
    return result


def _entry_from_data(entry_data: Dict[str, Any]) -> RegistryEntry:
    """Build a RegistryEntry from a parsed YAML dict."""
    return RegistryEntry(
        setup=entry_data.get("setup", ""),
        flags=entry_data.get("flags", ""),
        cleanup=entry_data.get("cleanup", ""),
        fields=_parse_fields(entry_data.get("fields")),
        installs_python_packages=bool(
            entry_data.get("installs_python_packages", False)
        ),
    )


def _load_builtin_registry() -> Dict[str, Dict[str, RegistryEntry]]:
    """Load all built-in registry YAML files."""
    registry: Dict[str, Dict[str, RegistryEntry]] = {}

    if not _REGISTRY_DIR.is_dir():
        return registry

    for yaml_file in sorted(_REGISTRY_DIR.glob("*.yaml")):
        tool_name = yaml_file.stem
        with open(yaml_file) as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            continue
        registry[tool_name] = {}
        for subcommand, entry_data in data.items():
            if not isinstance(entry_data, dict):
                continue
            registry[tool_name][subcommand] = _entry_from_data(entry_data)

    return registry


def load_registry(
    project_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, RegistryEntry]]:
    """Load the command registry with optional project overrides.

    Project overrides replace built-in entries at the command path level
    (not deep merge).
    """
    registry = _load_builtin_registry()

    if project_overrides:
        for tool_name, subcommands in project_overrides.items():
            if not isinstance(subcommands, dict):
                continue
            if tool_name not in registry:
                registry[tool_name] = {}
            for subcommand, entry_data in subcommands.items():
                if not isinstance(entry_data, dict):
                    continue
                registry[tool_name][subcommand] = _entry_from_data(entry_data)

    return registry


def lookup(
    registry: Dict[str, Dict[str, RegistryEntry]],
    tool: str,
    subcommand: str,
) -> Optional[RegistryEntry]:
    """Look up a registry entry by tool and subcommand."""
    tool_entries = registry.get(tool)
    if tool_entries is None:
        return None
    return tool_entries.get(subcommand)
