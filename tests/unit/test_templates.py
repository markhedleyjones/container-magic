"""Tests for template detection and resolution utilities."""

import pytest

from container_magic.core.config import StageConfig
from container_magic.core.templates import (
    detect_package_manager,
    detect_shell,
    detect_user_creation_style,
    resolve_base_image,
    resolve_distro,
)


# --- resolve_base_image ---


class TestResolveBaseImage:
    def test_direct_image(self):
        """A Docker image (contains ':') resolves to itself."""
        stages = {}
        assert resolve_base_image("python:3-slim", stages) == "python:3-slim"

    def test_direct_image_with_registry(self):
        """A Docker image with registry path resolves to itself."""
        stages = {}
        assert resolve_base_image("ghcr.io/org/image", stages) == "ghcr.io/org/image"

    def test_single_reference(self):
        """A stage name that points to a Docker image resolves through one hop."""
        stages = {"base": StageConfig(frm="alpine:3.19")}
        assert resolve_base_image("base", stages) == "alpine:3.19"

    def test_chained_references(self):
        """Multiple stage references resolve through the chain."""
        stages = {
            "base": StageConfig(frm="alpine:3.19"),
            "middle": StageConfig(frm="base"),
        }
        assert resolve_base_image("middle", stages) == "alpine:3.19"

    def test_circular_reference(self):
        """Circular stage references raise ValueError."""
        stages = {
            "a": StageConfig(frm="b"),
            "b": StageConfig(frm="a"),
        }
        with pytest.raises(ValueError, match="Circular stage reference"):
            resolve_base_image("a", stages)

    def test_missing_stage(self):
        """A reference to a non-existent stage (without ':' or '/') raises ValueError."""
        stages = {"base": StageConfig(frm="nonexistent")}
        with pytest.raises(ValueError, match="not found"):
            resolve_base_image("base", stages)


# --- detect_package_manager ---


class TestDetectPackageManager:
    def test_alpine(self):
        assert detect_package_manager("alpine:3.19") == "apk"

    def test_debian(self):
        assert detect_package_manager("debian:bookworm") == "apt"

    def test_ubuntu(self):
        assert detect_package_manager("ubuntu:22.04") == "apt"

    def test_python_slim(self):
        assert detect_package_manager("python:3-slim") == "apt"

    def test_fedora(self):
        assert detect_package_manager("fedora:39") == "dnf"

    def test_rocky(self):
        assert detect_package_manager("rockylinux:9") == "dnf"

    def test_centos(self):
        assert detect_package_manager("centos:stream9") == "dnf"


# --- detect_shell ---


class TestDetectShell:
    def test_alpine(self):
        assert detect_shell("alpine:3.19") == "/bin/sh"

    def test_non_alpine(self):
        assert detect_shell("python:3-slim") == "/bin/bash"

    def test_ubuntu(self):
        assert detect_shell("ubuntu:22.04") == "/bin/bash"


# --- detect_user_creation_style ---


class TestDetectUserCreationStyle:
    def test_alpine(self):
        assert detect_user_creation_style("alpine:3.19") == "alpine"

    def test_debian(self):
        assert detect_user_creation_style("debian:bookworm") == "standard"

    def test_fedora(self):
        assert detect_user_creation_style("fedora:39") == "standard"

    def test_python(self):
        assert detect_user_creation_style("python:3-slim") == "standard"


# --- resolve_distro ---


class TestResolveDistro:
    def test_none_returns_none(self):
        assert resolve_distro(None) is None

    def test_alpine(self):
        pm, shell, ucs = resolve_distro("alpine")
        assert pm == "apk"
        assert shell == "/bin/sh"
        assert ucs == "alpine"

    def test_debian(self):
        pm, shell, ucs = resolve_distro("debian")
        assert pm == "apt"
        assert shell == "/bin/bash"
        assert ucs == "standard"

    def test_ubuntu_maps_to_debian_family(self):
        pm, shell, ucs = resolve_distro("ubuntu")
        assert pm == "apt"
        assert ucs == "standard"

    def test_fedora(self):
        pm, shell, ucs = resolve_distro("fedora")
        assert pm == "dnf"
        assert ucs == "standard"

    def test_rhel_family(self):
        for name in ("centos", "rhel", "rocky", "alma"):
            pm, _, _ = resolve_distro(name)
            assert pm == "dnf", f"{name} should map to dnf"

    def test_case_insensitive(self):
        pm, shell, ucs = resolve_distro("Alpine")
        assert pm == "apk"
        pm, shell, ucs = resolve_distro("DEBIAN")
        assert pm == "apt"

    def test_unknown_warns_and_defaults_to_debian(self):
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            pm, shell, ucs = resolve_distro("gentoo")
            assert len(w) == 1
            assert "Unknown distro" in str(w[0].message)
            assert "gentoo" in str(w[0].message)
        assert pm == "apt"
        assert shell == "/bin/bash"
        assert ucs == "standard"
