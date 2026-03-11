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
    """Scan a workspace directory for external symlinks.

    Finds all symlinks within the workspace that point to targets outside
    the workspace directory. Internal symlinks (relative or absolute but
    still within the workspace) are left alone since they work naturally.

    Uses os.walk with followlinks=False and prunes symlinked directories
    from traversal to avoid walking into large external trees.

    Absolute symlinks pointing inside the workspace trigger a warning
    suggesting they be made relative for container compatibility.

    Circular and dangling symlinks are silently skipped.

    Args:
        workspace_path: Path to the workspace directory.

    Returns:
        Sorted list of relative paths within the workspace for external symlinks.
    """
    workspace_path = workspace_path.resolve()
    if not workspace_path.is_dir():
        return []

    workspace_str = str(workspace_path)
    external_symlinks: List[str] = []

    for dirpath, dirnames, filenames in os.walk(workspace_path, followlinks=False):
        # Check all entries (dirs and files) for symlinks
        for name in sorted(dirnames + filenames):
            full_path = os.path.join(dirpath, name)
            if not os.path.islink(full_path):
                continue

            rel_path = os.path.relpath(full_path, workspace_path)

            # Resolve to absolute path for classification
            try:
                resolved = str(Path(full_path).resolve(strict=True))
            except OSError:
                # Dangling or circular symlink
                continue

            if resolved.startswith(workspace_str + "/") or resolved == workspace_str:
                # Internal symlink - check if absolute (warn)
                raw_target = os.readlink(full_path)
                if os.path.isabs(raw_target):
                    logger.warning(
                        "Symlink %s uses an absolute path to a target inside the "
                        "workspace. Consider making it relative for container "
                        "compatibility: %s -> %s",
                        rel_path,
                        raw_target,
                        resolved,
                    )
            else:
                # External symlink - needs handling
                external_symlinks.append(rel_path)

        # Don't descend into symlinked directories (external or internal)
        dirnames[:] = sorted(
            d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))
        )

    return sorted(external_symlinks)
