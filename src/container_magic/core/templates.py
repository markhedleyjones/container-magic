"""Template detection and utilities."""

import warnings
from typing import Dict, Literal, Optional, Tuple

PackageManager = Literal["apt", "apk", "dnf"]
UserCreationStyle = Literal["alpine", "standard"]

# Distro family mappings: distro name -> (package_manager, shell, user_creation_style)
DISTRO_FAMILIES: Dict[str, Tuple[PackageManager, str, UserCreationStyle]] = {
    "alpine": ("apk", "/bin/sh", "alpine"),
    "debian": ("apt", "/bin/bash", "standard"),
    "ubuntu": ("apt", "/bin/bash", "standard"),
    "fedora": ("dnf", "/bin/bash", "standard"),
    "centos": ("dnf", "/bin/bash", "standard"),
    "rhel": ("dnf", "/bin/bash", "standard"),
    "rocky": ("dnf", "/bin/bash", "standard"),
    "alma": ("dnf", "/bin/bash", "standard"),
}

DEBIAN_DEFAULTS: Tuple[PackageManager, str, UserCreationStyle] = ("apt", "/bin/bash", "standard")


def resolve_distro(
    distro: Optional[str],
) -> Optional[Tuple[PackageManager, str, UserCreationStyle]]:
    """Resolve a distro name to its settings.

    Returns None if distro is None. Warns and defaults to Debian settings
    if the distro name is not recognised.
    """
    if distro is None:
        return None
    key = distro.lower()
    if key in DISTRO_FAMILIES:
        return DISTRO_FAMILIES[key]
    warnings.warn(
        f"Unknown distro '{distro}'. Defaulting to Debian settings. "
        f"Supported values: {', '.join(sorted(DISTRO_FAMILIES))}",
        stacklevel=2,
    )
    return DEBIAN_DEFAULTS


def resolve_distro_shell(stage_name: str, stages: Dict) -> Optional[str]:
    """Resolve the interactive shell from the distro field of a stage or its ancestors.

    Walks the from: chain looking for a distro field. Returns the shell
    component if found, None otherwise.
    """
    current = stage_name
    visited: set = set()
    while current in stages:
        if current in visited:
            break
        visited.add(current)
        stage = stages[current]
        if stage.distro:
            settings = resolve_distro(stage.distro)
            if settings:
                return settings[1]  # shell component
        frm = stage.frm
        if ":" in frm or "/" in frm:
            break
        current = frm
    return None


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
