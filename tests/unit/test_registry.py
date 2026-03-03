"""Tests for the command registry system."""

from container_magic.core.registry import RegistryEntry, load_registry, lookup


class TestBuiltinRegistry:
    def test_loads_apt_get(self):
        registry = load_registry()
        entry = lookup(registry, "apt-get", "install")
        assert entry is not None
        assert "-y" in entry.flags
        assert "--no-install-recommends" in entry.flags
        assert "rm -rf /var/lib/apt/lists/*" in entry.cleanup

    def test_loads_pip(self):
        registry = load_registry()
        entry = lookup(registry, "pip", "install")
        assert entry is not None
        assert "--no-cache-dir" in entry.flags
        assert entry.cleanup == ""

    def test_loads_apk(self):
        registry = load_registry()
        entry = lookup(registry, "apk", "add")
        assert entry is not None
        assert "--no-cache" in entry.flags
        assert entry.cleanup == ""

    def test_loads_dnf(self):
        registry = load_registry()
        entry = lookup(registry, "dnf", "install")
        assert entry is not None
        assert "-y" in entry.flags
        assert "dnf clean all" in entry.cleanup

    def test_unknown_tool_returns_none(self):
        registry = load_registry()
        assert lookup(registry, "nonexistent", "install") is None

    def test_unknown_subcommand_returns_none(self):
        registry = load_registry()
        assert lookup(registry, "apt-get", "nonexistent") is None


class TestProjectOverrides:
    def test_override_replaces_builtin(self):
        overrides = {
            "apt-get": {
                "install": {
                    "flags": "-y",
                },
            },
        }
        registry = load_registry(project_overrides=overrides)
        entry = lookup(registry, "apt-get", "install")
        assert entry is not None
        assert entry.flags == "-y"
        assert entry.cleanup == ""

    def test_override_adds_new_tool(self):
        overrides = {
            "my-tool": {
                "deploy": {
                    "flags": "--verbose",
                    "cleanup": "my-tool cleanup",
                },
            },
        }
        registry = load_registry(project_overrides=overrides)
        entry = lookup(registry, "my-tool", "deploy")
        assert entry is not None
        assert entry.flags == "--verbose"
        assert entry.cleanup == "my-tool cleanup"

    def test_override_preserves_other_tools(self):
        overrides = {
            "apt-get": {
                "install": {"flags": "-y"},
            },
        }
        registry = load_registry(project_overrides=overrides)
        pip_entry = lookup(registry, "pip", "install")
        assert pip_entry is not None
        assert "--no-cache-dir" in pip_entry.flags

    def test_override_preserves_other_subcommands(self):
        overrides = {
            "apt-get": {
                "update": {"flags": "--quiet"},
            },
        }
        registry = load_registry(project_overrides=overrides)
        install_entry = lookup(registry, "apt-get", "install")
        assert install_entry is not None
        assert "--no-install-recommends" in install_entry.flags
        update_entry = lookup(registry, "apt-get", "update")
        assert update_entry is not None
        assert update_entry.flags == "--quiet"

    def test_empty_overrides(self):
        registry = load_registry(project_overrides={})
        entry = lookup(registry, "apt-get", "install")
        assert entry is not None

    def test_none_overrides(self):
        registry = load_registry(project_overrides=None)
        entry = lookup(registry, "apt-get", "install")
        assert entry is not None


class TestRegistryEntry:
    def test_defaults(self):
        entry = RegistryEntry()
        assert entry.flags == ""
        assert entry.cleanup == ""

    def test_repr(self):
        entry = RegistryEntry(flags="-y", cleanup="rm -rf /tmp")
        assert "flags='-y'" in repr(entry)
        assert "cleanup='rm -rf /tmp'" in repr(entry)
