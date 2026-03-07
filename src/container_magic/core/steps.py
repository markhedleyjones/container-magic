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
from typing import Any, Dict, List, Optional, Union

from container_magic.core.registry import RegistryEntry


# Characters that need quoting in shell arguments
_SHELL_SPECIAL = re.compile(r'[>\<&|;*?$(){}[\]!#` \t\'"]')

# Container-magic keywords (underscore canonical form)
KEYWORDS: set = set()

# Removed keywords with migration messages
_REMOVED_KEYWORDS = {
    "copy_workspace": "Use 'copy: workspace' instead",
    "create_user": "Use 'create_user: <username>' instead",
    "become_user": "Use 'become: <username>' instead",
    "become_root": "Use 'become: root' instead",
    "copy_as_user": "Use 'copy' after 'become: <username>', or uppercase 'COPY --chown=...'",
    "copy_as_root": "Use 'copy' after 'become: root', or uppercase 'COPY'",
    "switch_user": "Use 'become: <username>' instead",
    "switch_root": "Use 'become: root' instead",
    "create-user": "Use 'create_user: <username>' instead",
    "become-user": "Use 'become: <username>' instead",
    "become-root": "Use 'become: root' instead",
    "copy-workspace": "Use 'copy: workspace' instead",
    "install_system_packages": "Remove this step; packages from the packages config are installed automatically",
    "install_pip_packages": "Remove this step; packages from the packages config are installed automatically",
    "copy_cached_assets": "Use project.assets with copy: steps instead",
    "copy-cached-assets": "Use project.assets with copy: steps instead",
}

# Known dict keys with special handling
_KNOWN_DICT_KEYS = {"run", "copy", "env", "create_user", "become"}

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
    - run: plain shell command (gets RUN prefix)
    - copy_v1: copy step with inline args
    """
    stripped = step.strip()

    # Check for copy steps with arguments (copy <args>)
    # Use the original step (not stripped) to detect trailing-space-only args
    prefix = "copy "
    if step.startswith(prefix) or stripped.startswith(prefix):
        args = (
            step[len(prefix) :].strip()
            if step.startswith(prefix)
            else stripped[len(prefix) :].strip()
        )
        if not args:
            raise ValueError("'copy' requires arguments (source and destination).")
        return {"type": "copy_v1", "args": args, "chown": "context"}

    # Canonical keywords
    if stripped in KEYWORDS:
        return {"type": "keyword", "keyword": stripped}

    # Removed keywords with migration messages
    if stripped in _REMOVED_KEYWORDS:
        raise ValueError(f"Unknown step '{stripped}'. {_REMOVED_KEYWORDS[stripped]}")

    # Uppercase Dockerfile instruction passthrough
    first_word = stripped.split()[0] if stripped.split() else ""
    if first_word in _DOCKERFILE_INSTRUCTIONS:
        return {"type": "passthrough", "command": stripped}

    # Check if it looks like an unknown keyword (lowercase, no spaces, no special chars)
    if re.match(r"^[a-z][a-z0-9_-]*$", stripped):
        all_known = KEYWORDS | set(_REMOVED_KEYWORDS.keys())
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
            f"Each step must have a single key, got {len(step)}: {list(step.keys())}"
        )

    key = next(iter(step))
    value = step[key]

    # Migration error for old {create: user} syntax
    if key == "create":
        raise ValueError(
            "'create: user' is no longer supported. Use 'create_user: <username>' instead."
        )

    # Dict steps: create_user and become
    if key == "create_user":
        if isinstance(value, str):
            if not value.strip():
                raise ValueError("'create_user' requires a non-empty username")
            return {
                "type": "create_user",
                "username": value.strip(),
                "uid": None,
                "gid": None,
            }
        elif isinstance(value, dict):
            if "name" not in value:
                raise ValueError("'create_user' dict must have a 'name' field")
            return {
                "type": "create_user",
                "username": value["name"],
                "uid": value.get("uid"),
                "gid": value.get("gid"),
            }
        else:
            raise ValueError(
                f"'create_user' value must be a string or dict, got {type(value).__name__}"
            )

    if key == "become":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("'become' requires a non-empty username string")
        return {"type": "become", "name": value.strip()}

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
        if isinstance(value, dict):
            return {"type": "env", "vars": value}
        elif isinstance(value, list):
            merged = {}
            for item in value:
                if isinstance(item, dict) and len(item) == 1:
                    merged.update(item)
                elif isinstance(item, str) and "=" in item:
                    k, v = item.split("=", 1)
                    merged[k.strip()] = v.strip()
                else:
                    raise ValueError(
                        f"'env' list items must be 'KEY=value' strings or single-key dicts, got: {item!r}"
                    )
            return {"type": "env", "vars": merged}
        else:
            raise ValueError(
                f"'env' value must be a dict or list, got {type(value).__name__}"
            )

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


def find_create_user_in_stages(stages) -> Optional[Dict[str, Any]]:
    """Find user info from create_user steps across all stages.

    Scans all stages for create_user steps and returns the first match.
    Handles both StageConfig objects and raw dicts.

    Returns {"username": str, "uid": int|None, "gid": int|None} or None.
    """
    for stage in stages.values() if isinstance(stages, dict) else stages:
        if isinstance(stage, dict):
            steps = stage.get("steps") or []
        else:
            steps = stage.steps or []

        for step in steps:
            if isinstance(step, dict) and "create_user" in step:
                value = step["create_user"]
                if isinstance(value, str):
                    return {"username": value, "uid": None, "gid": None}
                elif isinstance(value, dict):
                    return {
                        "username": value["name"],
                        "uid": value.get("uid"),
                        "gid": value.get("gid"),
                    }
    return None
