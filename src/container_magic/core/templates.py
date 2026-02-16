"""Template detection and utilities."""

from typing import Dict, Literal

PackageManager = Literal["apt", "apk", "dnf"]


def resolve_base_image(frm: str, stages: Dict) -> str:
    """Walk the stage chain until we find a Docker image (contains ':' or '/').

    Args:
        frm: The 'from' value — either a Docker image or another stage name.
        stages: Dict mapping stage names to stage configs (must have .frm attribute).

    Returns:
        The resolved Docker image name.

    Raises:
        ValueError: On circular references or missing stages.
    """
    visited: set = set()
    current = frm
    while current in stages:
        if current in visited:
            raise ValueError(f"Circular stage reference detected: {current}")
        visited.add(current)
        current = stages[current].frm
    if ":" in current or "/" in current:
        return current
    raise ValueError(f"Cannot resolve base image: stage '{current}' not found")


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
) -> Literal["alpine", "standard"]:
    """
    Detect user creation command style from base image.

    Args:
        base_image: Docker base image

    Returns:
        "alpine" for Alpine (BusyBox adduser), "standard" for everything else (useradd)
    """
    image_lower = base_image.lower()

    if "alpine" in image_lower:
        return "alpine"

    return "standard"
