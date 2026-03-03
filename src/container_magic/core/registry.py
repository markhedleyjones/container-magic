"""Command registry for structured step syntax.

Loads built-in command definitions from YAML files and merges with
per-project overrides. Provides lookup by command path (e.g. "apt-get.install")
to retrieve flags and cleanup commands.
"""

from pathlib import Path
from typing import Any, Dict, Optional

import yaml


_REGISTRY_DIR = Path(__file__).parent.parent / "registry"


class RegistryEntry:
    """A single registry entry with optional flags and cleanup."""

    def __init__(self, flags: str = "", cleanup: str = ""):
        self.flags = flags
        self.cleanup = cleanup

    def __repr__(self):
        return f"RegistryEntry(flags={self.flags!r}, cleanup={self.cleanup!r})"


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
            registry[tool_name][subcommand] = RegistryEntry(
                flags=entry_data.get("flags", ""),
                cleanup=entry_data.get("cleanup", ""),
            )

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
                registry[tool_name][subcommand] = RegistryEntry(
                    flags=entry_data.get("flags", ""),
                    cleanup=entry_data.get("cleanup", ""),
                )

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
