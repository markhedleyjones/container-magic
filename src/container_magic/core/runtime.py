"""Container runtime detection and utilities."""

import shutil
from enum import Enum
from typing import Optional


class Runtime(Enum):
    """Container runtime types."""

    DOCKER = "docker"
    PODMAN = "podman"


def detect_runtime() -> Optional[Runtime]:
    """
    Detect available container runtime.

    Prefers Docker if both are installed.

    Returns:
        Runtime enum or None if neither is found
    """
    if shutil.which("docker"):
        return Runtime.DOCKER
    elif shutil.which("podman"):
        return Runtime.PODMAN
    return None


def get_runtime(backend: str = "auto") -> Runtime:
    """
    Get container runtime based on configuration.

    Args:
        backend: 'auto', 'docker', or 'podman'

    Returns:
        Runtime enum

    Raises:
        RuntimeError: If requested runtime is not available
    """
    if backend == "auto":
        runtime = detect_runtime()
        if runtime is None:
            raise RuntimeError(
                "Neither Docker nor Podman found. Please install one of them."
            )
        return runtime
    elif backend == "docker":
        if not shutil.which("docker"):
            raise RuntimeError("Docker not found but explicitly requested")
        return Runtime.DOCKER
    elif backend == "podman":
        if not shutil.which("podman"):
            raise RuntimeError("Podman not found but explicitly requested")
        return Runtime.PODMAN
    else:
        raise ValueError(f"Invalid runtime backend: {backend}")
