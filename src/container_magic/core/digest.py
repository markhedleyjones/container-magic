"""Resolve a container image reference to its registry digest (best-effort).

Used for optional base-image pinning. Network-dependent and best-effort: any
failure (tool missing, offline, auth, timeout, unexpected output) returns None
so the caller falls back to the unpinned tag rather than breaking generation.
"""

import shutil
import subprocess
from typing import List, Optional

_TIMEOUT_SECONDS = 30


def _run(cmd: List[str]) -> Optional[str]:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=_TIMEOUT_SECONDS
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if result.returncode != 0:
        return None
    digest = result.stdout.strip()
    return digest if digest.startswith("sha256:") else None


def resolve_image_digest(ref: str) -> Optional[str]:
    """Return the ``sha256:...`` digest for an image ref, or None if unresolved.

    Tries ``skopeo`` (works for any registry without pulling), then
    ``docker buildx imagetools``. Returns None on any failure.
    """
    if shutil.which("skopeo"):
        digest = _run(
            ["skopeo", "inspect", f"docker://{ref}", "--format", "{{.Digest}}"]
        )
        if digest:
            return digest
    if shutil.which("docker"):
        digest = _run(
            [
                "docker",
                "buildx",
                "imagetools",
                "inspect",
                ref,
                "--format",
                "{{.Manifest.Digest}}",
            ]
        )
        if digest:
            return digest
    return None
