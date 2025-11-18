"""Template detection and utilities."""

from typing import Literal

PackageManager = Literal["apt", "apk", "dnf"]


def detect_package_manager(base_image: str) -> PackageManager:
    """
    Detect package manager from base image name.

    Args:
        base_image: Docker base image (e.g., "alpine:latest", "python:3-slim")

    Returns:
        Package manager type
    """
    image_lower = base_image.lower()

    # Alpine uses apk
    if "alpine" in image_lower:
        return "apk"

    # Fedora/CentOS/RHEL use dnf/yum
    if any(
        distro in image_lower
        for distro in ["fedora", "centos", "rhel", "rocky", "alma"]
    ):
        return "dnf"

    # Default to apt (Debian, Ubuntu, Python images are Debian-based)
    return "apt"


def detect_shell(base_image: str) -> str:
    """
    Detect default shell from base image.

    Args:
        base_image: Docker base image

    Returns:
        Shell path
    """
    image_lower = base_image.lower()

    # Alpine uses sh by default
    if "alpine" in image_lower:
        return "/bin/sh"

    # Most others have bash
    return "/bin/bash"


def detect_user_creation_style(
    base_image: str,
) -> Literal["debian", "alpine", "fedora"]:
    """
    Detect user creation command style from base image.

    Args:
        base_image: Docker base image

    Returns:
        User creation style
    """
    image_lower = base_image.lower()

    if "alpine" in image_lower:
        return "alpine"

    if any(
        distro in image_lower
        for distro in ["fedora", "centos", "rhel", "rocky", "alma"]
    ):
        return "fedora"

    return "debian"
