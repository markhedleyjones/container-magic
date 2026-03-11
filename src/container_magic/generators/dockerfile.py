"""Dockerfile generation from configuration."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from jinja2 import Environment, PackageLoader, select_autoescape

from container_magic.core.cache import build_asset_map
from container_magic.core.config import (
    ContainerMagicConfig,
    StageConfig,
)
from container_magic.core.registry import load_registry
from container_magic.core.steps import has_create_user_in_stages, parse_step
from container_magic.core.symlinks import scan_workspace_symlinks
from container_magic.core.templates import (
    detect_package_manager,
    detect_shell,
    detect_user_creation_style,
    resolve_base_image,
)


def _step_is_become(step: Union[str, Dict[str, Any]]) -> Optional[str]:
    """If the step is a become dict, return the target username. Otherwise None."""
    if isinstance(step, dict) and len(step) == 1 and "become" in step:
        return step["become"]
    return None


def _step_is_create_user(step: Union[str, Dict[str, Any]]) -> bool:
    """Check if a step is a {create: user} step."""
    return (
        isinstance(step, dict)
        and len(step) == 1
        and "create" in step
        and step["create"] == "user"
    )


def _get_parent_user_context(
    stage_name: str,
    stages_dict: Dict[str, StageConfig],
    production_user: str = "root",
) -> Optional[str]:
    """Get the user context from the parent stage hierarchy.

    Walks up the stage tree via `frm` references. For each stage, looks at the
    last become step. Returns the username if become is active, None otherwise.

    The keyword ``"user"`` in become steps is resolved to *production_user* so
    that callers receive the actual username rather than the raw keyword.
    """
    visited: set = set()
    current = stages_dict.get(stage_name)
    if current is None:
        return None

    parent_name = current.frm
    while parent_name in stages_dict:
        if parent_name in visited:
            break
        visited.add(parent_name)

        parent = stages_dict[parent_name]
        steps = parent.steps

        if steps is not None:
            last_user = None
            for step in steps:
                become_target = _step_is_become(step)
                if become_target is not None:
                    if become_target == "root":
                        last_user = None
                    elif become_target == "user":
                        last_user = production_user
                    else:
                        last_user = become_target
            if last_user is not None:
                return last_user

        if ":" in parent.frm or "/" in parent.frm:
            return None

        parent_name = parent.frm

    return None


def _has_create_user_in_hierarchy(
    stage_name: str,
    stages_dict: Dict[str, StageConfig],
) -> bool:
    """Check if create_user exists in any ancestor stage (including self)."""
    visited: set = set()
    current_name = stage_name

    while current_name in stages_dict:
        if current_name in visited:
            break
        visited.add(current_name)

        stage = stages_dict[current_name]
        if stage.steps:
            for step in stage.steps:
                if _step_is_create_user(step):
                    return True

        if ":" in stage.frm or "/" in stage.frm:
            return False
        current_name = stage.frm

    return False


def _stage_needs_user_args(ordered_steps: List[Dict]) -> bool:
    """Check if a stage's steps require user-related ARGs.

    Returns True if the stage has a create_user step or a become step that
    references ${USER_NAME} (meaning the configured user was created via ARGs).
    """
    for step in ordered_steps:
        if step["type"] == "create_user":
            return True
        if step["type"] == "become" and "${USER_NAME}" in step.get("name", ""):
            return True
    return False


def _merge_consecutive_env_steps(ordered_steps: List[Dict]) -> List[Dict]:
    """Merge consecutive env steps into single steps with combined vars."""
    if not ordered_steps:
        return ordered_steps

    merged = []
    for step in ordered_steps:
        if step["type"] == "env" and merged and merged[-1]["type"] == "env":
            merged[-1] = {
                "type": "env",
                "vars": {**merged[-1]["vars"], **step["vars"]},
            }
        else:
            merged.append(step)
    return merged


def _resolve_copy_source(args: str, asset_map: Dict[str, str]) -> str:
    """Rewrite copy source if it matches an asset filename.

    The args string is "source dest".
    If the source matches an asset filename, replace it with the cache path.
    """
    parts = args.split()
    if not parts:
        return args

    source = parts[0]
    if source in asset_map:
        parts[0] = asset_map[source]
        return " ".join(parts)

    return args


def process_stage_steps(
    stage: StageConfig,
    stage_name: str,
    project_dir: Path,
    stages_dict: Dict[str, StageConfig],
    production_user: str,
    workspace_name: str,
    registry: Dict = None,
    asset_map: Dict[str, str] = None,
    workspace_symlinks: List[tuple] = None,
) -> List[Dict]:
    """Process build steps for a stage.

    When asset_map is provided, copy sources matching asset filenames are
    rewritten to their cache paths.

    When workspace_symlinks is provided, copy_workspace steps include
    symlink overlay data for the Dockerfile template.

    Returns:
        ordered_steps list
    """
    if registry is None:
        registry = load_registry()
    if asset_map is None:
        asset_map = {}
    if workspace_symlinks is None:
        workspace_symlinks = []

    # Default build order if not specified
    is_default_production = False
    if stage.steps is None:
        if ":" in stage.frm or "/" in stage.frm:
            return []
        else:
            steps: List[Union[str, Dict[str, Any]]] = []
            if stage_name == "production":
                steps = [{"copy": "workspace"}]
                is_default_production = True
    else:
        steps = list(stage.steps)

    # When the configured user is created via create_user (which uses ARGs),
    # become and chown must reference ${USER_NAME} instead of the literal name,
    # because development builds pass the host username as USER_NAME.
    user_created_via_args = _has_create_user_in_hierarchy(stage_name, stages_dict)

    def _resolve_user_ref(name: str) -> str:
        """Return ${USER_NAME} if the name matches the configured user created via ARGs."""
        if name == production_user and user_created_via_args:
            return "${USER_NAME}"
        return name

    # Track current user context: None = root, string = username or ${USER_NAME}
    parent_context = _get_parent_user_context(stage_name, stages_dict, production_user)
    if parent_context is not None:
        current_user = _resolve_user_ref(parent_context)
    else:
        current_user = None

    # For default production steps, use configured user for workspace ownership.
    # Use literal username (not ARG) since production stage won't have ARGs declared.
    if is_default_production and current_user is None and production_user != "root":
        current_user = production_user

    ordered_steps = []

    for step in steps:
        parsed = parse_step(step, registry)

        step_type = parsed["type"]

        if step_type == "create_user":
            ordered_steps.append({"type": "create_user"})
            user_created_via_args = True

        elif step_type == "create_user_literal":
            ordered_steps.append(
                {"type": "create_user_literal", "name": parsed["name"]}
            )

        elif step_type == "become":
            name = parsed["name"]
            if name == "user":
                # Keyword 'user' resolves to the configured production user
                current_user = _resolve_user_ref(production_user)
                ordered_steps.append({"type": "become", "name": current_user or "root"})
            elif name == "root":
                current_user = None
                ordered_steps.append({"type": "become", "name": "root"})
            else:
                current_user = _resolve_user_ref(name)
                ordered_steps.append({"type": "become", "name": current_user or "root"})

        elif step_type == "copy_v1":
            chown = parsed["chown"]
            if chown == "context":
                chown = current_user
            args = _resolve_copy_source(parsed["args"], asset_map)
            ordered_steps.append({"type": "copy", "args": args, "chown": chown})

        elif step_type == "copy_v2":
            for args in parsed["args_list"]:
                resolved_args = _resolve_copy_source(args, asset_map)
                # Single token matching workspace name becomes copy_workspace
                if args.strip() == workspace_name:
                    symlink_data = [{"rel_path": rel} for rel in workspace_symlinks]
                    ordered_steps.append(
                        {
                            "type": "copy_workspace",
                            "chown": current_user,
                            "symlinks": symlink_data,
                        }
                    )
                else:
                    ordered_steps.append(
                        {"type": "copy", "args": resolved_args, "chown": current_user}
                    )

        elif step_type == "env":
            ordered_steps.append({"type": "env", "vars": parsed["vars"]})

        elif step_type == "run":
            command = parsed["command"]
            if "\n" in command and "\\\n" not in command:
                lines = [line for line in command.splitlines() if line.strip()]
                command = " && \\\n    ".join(lines)
            ordered_steps.append({"type": "custom", "command": command})

        elif step_type == "passthrough":
            ordered_steps.append({"type": "custom", "command": parsed["command"]})

    return ordered_steps


def generate_dockerfile(
    config: ContainerMagicConfig, output_path: Path, workspace_symlinks=None
) -> None:
    """Generate Dockerfile from configuration."""
    env = Environment(
        loader=PackageLoader("container_magic", "templates"),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )

    template = env.get_template("Dockerfile.j2")

    # Build stages dict with defaults if needed
    stages = dict(config.stages)

    # Get user info from config.names
    has_user = has_create_user_in_stages(stages)
    user_name = config.names.user

    if "development" not in stages:
        from container_magic.core.config import StageConfig

        dev_steps = []
        if has_user:
            dev_steps.append({"become": "user"})
        stages["development"] = StageConfig(frm="base", steps=dev_steps)

    if "production" not in stages:
        from container_magic.core.config import StageConfig

        stages["production"] = StageConfig(frm="base")

    registry = load_registry(
        project_overrides=config.command_registry if config.command_registry else None
    )

    # Build asset map from root-level assets
    project_dir = output_path.parent
    asset_map = build_asset_map(project_dir, config.assets)

    # Scan workspace for external symlinks (unless pre-scanned)
    if workspace_symlinks is None:
        workspace_path = project_dir / config.names.workspace
        workspace_symlinks = scan_workspace_symlinks(workspace_path)

    user_uid = 1000 if has_user else 0
    user_gid = 1000 if has_user else 0
    user_home = f"/home/{user_name}" if has_user else "/root"

    stages_data = []
    for stage_name, stage_config in stages.items():
        base_image = stage_config.frm
        resolved_image = resolve_base_image(base_image, stages)
        package_manager = stage_config.package_manager or detect_package_manager(
            resolved_image
        )
        shell = stage_config.shell or detect_shell(resolved_image)
        user_creation_style = detect_user_creation_style(resolved_image)

        ordered_steps = process_stage_steps(
            stage_config,
            stage_name,
            project_dir,
            stages,
            user_name,
            config.names.workspace,
            registry,
            asset_map,
            workspace_symlinks,
        )

        ordered_steps = _merge_consecutive_env_steps(ordered_steps)

        needs_user_args = _stage_needs_user_args(ordered_steps)
        from_is_image = ":" in base_image or "/" in base_image

        stages_data.append(
            {
                "name": stage_name,
                "from": base_image,
                "from_is_image": from_is_image,
                "package_manager": package_manager,
                "shell": shell,
                "user_creation_style": user_creation_style,
                "user": user_name,
                "user_uid": user_uid,
                "user_gid": user_gid,
                "user_home": user_home,
                "ordered_steps": ordered_steps,
                "needs_user_args": needs_user_args,
            }
        )

    dockerfile_content = template.render(
        stages=stages_data,
        workspace_name=config.names.workspace,
    )

    with open(output_path, "w") as f:
        f.write(dockerfile_content)
