"""Step parsing and command flattening for structured step syntax (v2).

Three step categories determined by YAML structure:

1. Bare string - container-magic keyword (create_user, become_user, etc.)
   or uppercase Dockerfile passthrough (EXPOSE 8080, etc.)

2. Dict with known key - structured steps with special handling:
   - run: string or list, generates RUN
   - copy: string or list, generates COPY lines (with --chown if user active)
   - env: dict of key/value, generates ENV lines

3. Dict with any other key - command builder. Keys flatten into command,
   list items become arguments. Registry lookup for flags and cleanup.
"""

import difflib
import re
import warnings
from typing import Any, Dict, List, Optional, Union

from container_magic.core.registry import RegistryEntry


# Characters that need quoting in shell arguments
_SHELL_SPECIAL = re.compile(r'[>\<&|;*?$(){}[\]!#` \t\'"]')

# Container-magic keywords (underscore canonical form)
KEYWORDS = {
    "create_user",
    "become_user",
    "become_root",
    "copy_workspace",
}

# Deprecated keywords that still parse but emit warnings
_DEPRECATED_KEYWORDS = {
    "copy_cached_assets",
}

# Accepted aliases mapped to canonical form (no deprecation warnings)
_KEYWORD_ALIASES = {
    "create-user": "create_user",
    "become-user": "become_user",
    "switch_user": "become_user",
    "become-root": "become_root",
    "switch_root": "become_root",
    "copy-workspace": "copy_workspace",
    "copy-cached-assets": "copy_cached_assets",
}

# v1 keywords that get converted to v2 equivalents
_V1_STEP_KEYWORDS = {
    "install_system_packages",
    "install_pip_packages",
}

# Known dict keys with special handling
_KNOWN_DICT_KEYS = {"run", "copy", "env"}

# Dockerfile instructions that should pass through without RUN prefix
_DOCKERFILE_INSTRUCTIONS = {
    "ADD",
    "ARG",
    "CMD",
    "COPY",
    "ENTRYPOINT",
    "ENV",
    "EXPOSE",
    "FROM",
    "HEALTHCHECK",
    "LABEL",
    "RUN",
    "SHELL",
    "STOPSIGNAL",
    "USER",
    "VOLUME",
    "WORKDIR",
}


def quote_arg(arg: str) -> str:
    """Quote a shell argument if it contains special characters."""
    if _SHELL_SPECIAL.search(arg):
        escaped = arg.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return arg


def flatten_command(node: Any, segments: Optional[List[str]] = None) -> List[str]:
    """Recursively flatten a dict/list/string structure into command segments.

    - Dict key becomes a command segment
    - String value becomes an argument
    - List value becomes the argument list
    - Nested dict recurses deeper
    - None/empty value contributes nothing (just the key)
    """
    if segments is None:
        segments = []

    if node is None:
        return segments
    elif isinstance(node, str):
        segments.append(node)
    elif isinstance(node, (int, float)):
        segments.append(str(node))
    elif isinstance(node, list):
        for item in node:
            if isinstance(item, str):
                segments.append(quote_arg(item))
            elif isinstance(item, (int, float)):
                segments.append(str(item))
            elif isinstance(item, dict):
                flatten_command(item, segments)
            elif item is not None:
                segments.append(str(item))
    elif isinstance(node, dict):
        for key, value in node.items():
            segments.append(str(key))
            flatten_command(value, segments)

    return segments


def build_command(
    tool: str,
    body: Any,
    registry_entry: Optional[RegistryEntry] = None,
) -> str:
    """Build a complete RUN command from a tool name and its body.

    Flattens the dict structure into a command, injects registry flags
    after the subcommand, and appends cleanup if present.
    """
    segments = [tool]

    if registry_entry is not None and isinstance(body, dict) and len(body) == 1:
        subcommand = next(iter(body))
        args_value = body[subcommand]
        segments.append(subcommand)
        if registry_entry.flags:
            segments.append(registry_entry.flags)
        if isinstance(args_value, list):
            if len(args_value) > 1:
                base = " ".join(segments)
                items = " \\\n        ".join(
                    quote_arg(str(item)) for item in args_value
                )
                command = f"{base} \\\n        {items}"
            else:
                for item in args_value:
                    segments.append(quote_arg(str(item)))
                command = " ".join(segments)
        elif isinstance(args_value, str):
            segments.append(args_value)
            command = " ".join(segments)
        elif isinstance(args_value, dict):
            flatten_command(args_value, segments)
            command = " ".join(segments)
        elif args_value is not None:
            segments.append(str(args_value))
            command = " ".join(segments)
        else:
            command = " ".join(segments)
        if registry_entry.setup:
            command = f"{registry_entry.setup} && \\\n    {command}"
        if registry_entry.cleanup:
            command = f"{command} && \\\n    {registry_entry.cleanup}"
        return command

    # No registry entry or complex body - just flatten
    flatten_command(body, segments)
    command = " ".join(segments)
    return command


def classify_bare_string(step: str) -> Dict[str, Any]:
    """Classify a bare string step.

    Returns a step dict with type information:
    - keyword: container-magic keyword (create_user, become_user, etc.)
    - passthrough: uppercase Dockerfile instruction
    - v1_keyword: legacy v1 keyword (install_system_packages, etc.)
    - run: plain shell command (gets RUN prefix)
    - copy_v1: v1-style copy step with inline args
    """
    stripped = step.strip()

    # Check for copy steps with arguments (copy <args>, copy_as_user <args>, copy_as_root <args>)
    # Use the original step (not stripped) to detect trailing-space-only args
    for prefix in ("copy_as_user ", "copy_as_root ", "copy "):
        if step.startswith(prefix) or stripped.startswith(prefix):
            args = (
                step[len(prefix) :].strip()
                if step.startswith(prefix)
                else stripped[len(prefix) :].strip()
            )
            if not args:
                raise ValueError(
                    f"'{prefix.strip()}' requires arguments (source and destination)."
                )
            if prefix == "copy_as_user ":
                return {"type": "copy_v1", "args": args, "chown": True}
            elif prefix == "copy_as_root ":
                return {"type": "copy_v1", "args": args, "chown": False}
            else:
                return {"type": "copy_v1", "args": args, "chown": "context"}

    # Canonical keywords
    if stripped in KEYWORDS:
        return {"type": "keyword", "keyword": stripped}

    # Deprecated keywords
    if stripped in _DEPRECATED_KEYWORDS:
        warnings.warn(
            f"Step '{stripped}' is deprecated. "
            "Move assets to project.assets and use copy: steps instead.",
            DeprecationWarning,
            stacklevel=4,
        )
        return {"type": "keyword", "keyword": stripped}

    # Accepted aliases (hyphens, switch_user/switch_root) - no deprecation
    if stripped in _KEYWORD_ALIASES:
        canonical = _KEYWORD_ALIASES[stripped]
        if canonical in _DEPRECATED_KEYWORDS:
            warnings.warn(
                f"Step '{stripped}' is deprecated. "
                "Move assets to project.assets and use copy: steps instead.",
                DeprecationWarning,
                stacklevel=4,
            )
        return {"type": "keyword", "keyword": canonical}

    # v1 step keywords
    if stripped in _V1_STEP_KEYWORDS:
        warnings.warn(
            f"Step '{stripped}' is deprecated, use structured step syntax instead",
            DeprecationWarning,
            stacklevel=4,
        )
        return {"type": "v1_keyword", "keyword": stripped}

    # Uppercase Dockerfile instruction passthrough
    first_word = stripped.split()[0] if stripped.split() else ""
    if first_word in _DOCKERFILE_INSTRUCTIONS:
        return {"type": "passthrough", "command": stripped}

    # Check if it looks like an unknown keyword (lowercase, no spaces, no special chars)
    if re.match(r"^[a-z][a-z0-9_-]*$", stripped):
        all_known = (
            KEYWORDS
            | _DEPRECATED_KEYWORDS
            | set(_KEYWORD_ALIASES.keys())
            | _V1_STEP_KEYWORDS
        )
        matches = difflib.get_close_matches(stripped, all_known, n=3, cutoff=0.6)
        if matches:
            suggestion = f" Did you mean: {', '.join(matches)}?"
        else:
            suggestion = ""
        raise ValueError(f"Unknown step keyword '{stripped}'.{suggestion}")

    # Plain shell command
    return {"type": "run", "command": stripped}


def parse_dict_step(
    step: Dict[str, Any],
    registry: Dict,
) -> Dict[str, Any]:
    """Parse a dict step into a processed step dict.

    Known keys (run, copy, env) get special handling.
    Other keys go through the command builder with registry lookup.
    """
    if len(step) != 1:
        raise ValueError(
            f"Dict step must have exactly one key, got {len(step)}: {list(step.keys())}"
        )

    key = next(iter(step))
    value = step[key]

    # Known dict keys with special handling
    if key == "run":
        if isinstance(value, list):
            command = " && \\\n    ".join(str(v) for v in value)
        else:
            command = str(value)
        return {"type": "run", "command": command}

    if key == "copy":
        if isinstance(value, str):
            return {"type": "copy_v2", "args_list": [value]}
        elif isinstance(value, list):
            return {"type": "copy_v2", "args_list": [str(v) for v in value]}
        else:
            raise ValueError(
                f"'copy' value must be a string or list, got {type(value).__name__}"
            )

    if key == "env":
        if not isinstance(value, dict):
            raise ValueError(f"'env' value must be a dict, got {type(value).__name__}")
        return {"type": "env", "vars": value}

    # Command builder - look up in registry
    from container_magic.core.registry import lookup as registry_lookup

    # Determine subcommand for registry lookup
    subcommand = None
    if isinstance(value, dict) and len(value) == 1:
        subcommand = next(iter(value))

    entry = None
    if subcommand is not None:
        entry = registry_lookup(registry, key, subcommand)

    command = build_command(key, value, entry)
    return {"type": "run", "command": command}


def parse_step(
    step: Union[str, Dict[str, Any]],
    registry: Dict,
) -> Dict[str, Any]:
    """Parse a single step (string or dict) into a processed step dict."""
    if isinstance(step, str):
        return classify_bare_string(step)
    elif isinstance(step, dict):
        return parse_dict_step(step, registry)
    else:
        raise ValueError(f"Step must be a string or dict, got {type(step).__name__}")
