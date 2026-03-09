"""Symlink scanning for workspace directories.

Detects external symlinks that need special handling for Docker builds
and container bind mounts.
"""

import logging
import os
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


def scan_workspace_symlinks(
    workspace_path: Path,
) -> List[str]:
    """Recursively scan a workspace directory for external symlinks.

    Finds all symlinks within the workspace that point to targets outside
    the workspace directory. Internal symlinks (relative or absolute but
    still within the workspace) are left alone since they work naturally.

    Absolute symlinks pointing inside the workspace trigger a warning
    suggesting they be made relative for container compatibility.

    Circular and dangling symlinks are silently skipped.

    Args:
        workspace_path: Path to the workspace directory.

    Returns:
        List of relative paths within the workspace for external symlinks.
    """
    workspace_path = workspace_path.resolve()
    if not workspace_path.is_dir():
        return []

    external_symlinks: List[str] = []
    # Track external symlink paths so we skip anything nested beneath them
    external_prefixes: List[str] = []

    for item in sorted(workspace_path.rglob("*")):
        if not item.is_symlink():
            continue

        rel_path = str(item.relative_to(workspace_path))

        # Skip items nested under an already-found external symlink
        if any(rel_path.startswith(prefix + "/") for prefix in external_prefixes):
            continue

        # Read the raw link target (before resolution)
        raw_target = Path(os.readlink(item))

        # Resolve to absolute path for classification
        try:
            resolved = item.resolve(strict=True)
        except OSError:
            # Dangling or circular symlink
            continue

        # Classify: is the resolved target inside or outside the workspace?
        try:
            resolved.relative_to(workspace_path)
        except ValueError:
            # External symlink - needs handling
            external_symlinks.append(rel_path)
            external_prefixes.append(rel_path)
        else:
            # Internal symlink - check if absolute (warn)
            if raw_target.is_absolute():
                logger.warning(
                    "Symlink %s uses an absolute path to a target inside the "
                    "workspace. Consider making it relative for container "
                    "compatibility: %s -> %s",
                    item.relative_to(workspace_path),
                    raw_target,
                    resolved,
                )

    return external_symlinks
