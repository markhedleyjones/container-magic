"""Volume string helpers for SELinux labelling and variable expansion."""

import re
import sys
from dataclasses import dataclass
from typing import List, Optional

SHORTHAND_CONTAINER_PREFIX = "/data"
_SHORTHAND_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def is_shorthand_volume(volume: str) -> bool:
    """Return True if the volume string is shorthand (a bare name, no colon)."""
    return ":" not in volume


def validate_shorthand_name(name: str) -> None:
    """Raise ValueError if a shorthand volume name is malformed."""
    if not _SHORTHAND_NAME_PATTERN.match(name):
        raise ValueError(
            f"Invalid shorthand volume '{name}': bare names must match "
            f"[a-zA-Z0-9_-]+. Use 'host:container' for anything else."
        )


def shorthand_names(volumes: List[str]) -> List[str]:
    """Return the bare names of shorthand entries from a volumes list."""
    return [v for v in volumes if is_shorthand_volume(v)]


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


@dataclass
class VolumeContext:
    """Context for resolving volume variables.

    user_home: home directory of the user running the command.
    container_home: home directory inside the container.
    workspace_user: absolute workspace path on the user side (only for cm run).
    workspace_container: absolute workspace path inside the container.
    project_dir: absolute project root on the user side, used to resolve
        shorthand volumes to an absolute host path.
    """

    user_home: str
    container_home: str
    workspace_user: Optional[str] = None
    workspace_container: Optional[str] = None
    project_dir: Optional[str] = None


_VARIABLE_PATTERN = re.compile(r"^(?:~(?=/|$)|\$HOME(?=/|$)|\$WORKSPACE(?=/|$))")


def _has_workspace_variable(path: str) -> bool:
    """Check whether a path contains a $WORKSPACE reference."""
    return "$WORKSPACE" in path


def _expand_side(path: str, home: str, workspace: Optional[str]) -> str:
    """Expand variables in one side (user or container) of a volume string."""

    def _replace(match: re.Match) -> str:
        token = match.group(0)
        if token in ("~", "$HOME"):
            return home
        if token == "$WORKSPACE":
            if workspace is None:
                return token
            return workspace
        return token

    return _VARIABLE_PATTERN.sub(_replace, path)


def expand_volume(volume: str, context: VolumeContext) -> str:
    """Expand ~ , $HOME, $WORKSPACE, and shorthand in a volume string.

    Shorthand (a bare name like 'outputs') expands to
    '{project_dir}/{name}:/data/{name}'. For explicit host:container strings,
    each side of the colon is expanded independently using the appropriate
    home and workspace paths.
    """
    if is_shorthand_volume(volume):
        validate_shorthand_name(volume)
        host_base = context.project_dir or "."
        return f"{host_base}/{volume}:{SHORTHAND_CONTAINER_PREFIX}/{volume}"

    parts = volume.split(":")
    if len(parts) < 2:
        return volume

    user_path = _expand_side(parts[0], context.user_home, context.workspace_user)
    container_path = _expand_side(
        parts[1], context.container_home, context.workspace_container
    )

    expanded_parts = [user_path, container_path] + parts[2:]
    return ":".join(expanded_parts)


def expand_volumes_for_run(volumes: List[str], context: VolumeContext) -> List[str]:
    """Expand variables in volumes for cm run (development)."""
    return [expand_volume(v, context) for v in volumes]


def expand_volumes_for_script(volumes: List[str], container_home: str) -> List[str]:
    """Expand variables in volumes for run.sh generation (production).

    User-side ~ and $HOME are rendered as $HOME for shell expansion at runtime.
    Volumes containing $WORKSPACE are filtered out with a warning.
    """
    result = []
    for volume in volumes:
        if is_shorthand_volume(volume):
            validate_shorthand_name(volume)
            result.append(
                f"${{_RUN_SH_DIR}}/{volume}:{SHORTHAND_CONTAINER_PREFIX}/{volume}"
            )
            continue

        if _has_workspace_variable(volume):
            print(
                f"Warning: Volume '{volume}' uses $WORKSPACE and will only "
                f"apply during development (cm run). The generated run.sh does "
                f"not include it because the workspace is expected to be baked "
                f"into the production image.",
                file=sys.stderr,
            )
            continue

        parts = volume.split(":")
        if len(parts) < 2:
            result.append(volume)
            continue

        user_path = _expand_side(parts[0], "$HOME", workspace=None)
        container_path = _expand_side(parts[1], container_home, workspace=None)
        expanded_parts = [user_path, container_path] + parts[2:]
        result.append(":".join(expanded_parts))

    return result


def expand_mount_path(path: str, context: VolumeContext) -> str:
    """Expand variables in a single mount path (user side only).

    Used for custom command mount paths provided at runtime.
    """
    return _expand_side(path, context.user_home, context.workspace_user)
