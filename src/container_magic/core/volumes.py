"""Volume string helpers for SELinux labelling."""

from typing import List


def ensure_selinux_label(volume: str) -> str:
    """Append an SELinux :z label to a volume string if not already present.

    Handles the standard host:container[:options] format:
    - /host:/container          -> /host:/container:z
    - /host:/container:ro       -> /host:/container:ro,z
    - /host:/container:z        -> unchanged
    - /host:/container:ro,z     -> unchanged
    - /host:/container:Z        -> unchanged
    """
    parts = volume.split(":")
    if len(parts) < 2:
        return volume

    if len(parts) == 2:
        return volume + ":z"

    options = parts[-1]
    option_tokens = [t.strip() for t in options.split(",")]
    if "z" in option_tokens or "Z" in option_tokens:
        return volume

    return volume + ",z"


def label_volumes(volumes: List[str]) -> List[str]:
    """Apply SELinux labelling to a list of volume strings."""
    return [ensure_selinux_label(v) for v in volumes]
