"""Volume string helpers for SELinux labelling and variable expansion."""

import os
import re
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

SHORTHAND_CONTAINER_PREFIX = "/data"
_SHORTHAND_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def is_shorthand_volume(volume: str) -> bool:
    """Return True if the volume string has no colon (shorthand form)."""
    return ":" not in volume


def validate_shorthand_basename(name: str) -> None:
    """Raise ValueError if a shorthand basename is not a valid identifier."""
    if not _SHORTHAND_NAME_PATTERN.match(name):
        raise ValueError(
            f"Invalid shorthand volume basename '{name}': must match "
            f"[a-zA-Z0-9_-]+. Use 'host:container' for custom container paths."
        )


def parse_shorthand(host_path: str) -> Tuple[str, str]:
    """Parse a shorthand host path into (cleaned_host, basename).

    Strips trailing slashes. Raises ValueError if the basename is not a valid
    identifier or the host path is empty.
    """
    cleaned = host_path.rstrip("/")
    if not cleaned:
        raise ValueError(f"Invalid shorthand volume '{host_path}': host path is empty")
    basename = cleaned.rsplit("/", 1)[-1]
    validate_shorthand_basename(basename)
    return cleaned, basename


def _host_needs_anchor(path: str) -> bool:
    """Return True if a host path needs project / run.sh-dir anchoring.

    Relative paths (bare names, './x', '../x') need anchoring. Absolute paths,
    '~' and '$' prefixes are self-sufficient and are left alone.
    """
    if not path:
        return False
    return not (path.startswith(("/", "~", "$")))


def shorthand_anchored_paths(volumes: List[str]) -> List[str]:
    """Return cleaned host paths for shorthand entries that need mkdir.

    Only relative host paths (bare names and './' / '../' prefixes) are
    returned. Absolute and '~' / '$' prefixed paths are the caller's
    responsibility.
    """
    result = []
    for v in volumes:
        if not is_shorthand_volume(v):
            continue
        host, _ = parse_shorthand(v)
        if _host_needs_anchor(host):
            result.append(host)
    return result


def shorthand_container_path(volume: str) -> str:
    """Return the container-side path for a shorthand volume."""
    _, basename = parse_shorthand(volume)
    return f"{SHORTHAND_CONTAINER_PREFIX}/{basename}"


def container_path_of(volume: str) -> str:
    """Return the container-side path for any volume entry (shorthand or full)."""
    if is_shorthand_volume(volume):
        return shorthand_container_path(volume)
    return volume.split(":")[1]


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

    Shorthand (no colon) expands to '<host>:/data/<basename>'. Relative host
    paths are anchored to project_dir; absolute and '~' / '$' prefixes are
    self-sufficient and use normal variable expansion.
    """
    if is_shorthand_volume(volume):
        host, basename = parse_shorthand(volume)
        container = f"{SHORTHAND_CONTAINER_PREFIX}/{basename}"
        if _host_needs_anchor(host):
            host_base = context.project_dir or "."
            resolved = f"{host_base}/{host}"
            if context.project_dir and os.path.isabs(context.project_dir):
                resolved = os.path.normpath(resolved)
            return f"{resolved}:{container}"
        expanded_host = _expand_side(host, context.user_home, context.workspace_user)
        return f"{expanded_host}:{container}"

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
            host, basename = parse_shorthand(volume)
            container = f"{SHORTHAND_CONTAINER_PREFIX}/{basename}"
            if _host_needs_anchor(host):
                result.append(f"${{_RUN_SH_DIR}}/{host}:{container}")
                continue
            if _has_workspace_variable(host):
                print(
                    f"Warning: Volume '{volume}' uses $WORKSPACE and will only "
                    f"apply during development (cm run). The generated run.sh "
                    f"does not include it because the workspace is expected to "
                    f"be baked into the production image.",
                    file=sys.stderr,
                )
                continue
            expanded_host = _expand_side(host, "$HOME", workspace=None)
            result.append(f"{expanded_host}:{container}")
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
