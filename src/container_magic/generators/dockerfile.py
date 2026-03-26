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
    detect_user_creation_style,
    resolve_base_image,
    resolve_distro,
    resolve_inherited_distro,
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


def _step_is_pip(step: Union[str, Dict[str, Any]]) -> bool:
    """Check if a raw step is a pip step."""
    return isinstance(step, dict) and len(step) == 1 and next(iter(step)) == "pip"


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
    venv_active: bool = False,
    implicit_user: bool = False,
) -> tuple:
    """Process build steps for a stage.

    When asset_map is provided, copy sources matching asset filenames are
    rewritten to their cache paths.

    When workspace_symlinks is provided, copy_workspace steps include
    symlink overlay data for the Dockerfile template.

    Returns:
        (ordered_steps, venv_active) tuple
    """
    if registry is None:
        registry = load_registry()
    if asset_map is None:
        asset_map = {}
    if workspace_symlinks is None:
        workspace_symlinks = []

    # Default build order if not specified
    if stage.steps is None:
        if ":" in stage.frm or "/" in stage.frm:
            return [], venv_active
        else:
            steps: List[Union[str, Dict[str, Any]]] = []
            if stage_name == "production":
                steps = [{"copy": "workspace"}]
    else:
        steps = list(stage.steps)

    # When the configured user is created via create_user (which uses ARGs),
    # become and chown must reference ${USER_NAME} instead of the literal name,
    # because development builds pass the host username as USER_NAME.
    user_created_via_args = (
        _has_create_user_in_hierarchy(stage_name, stages_dict) or implicit_user
    )

    def _resolve_user_ref(name: str) -> str:
        """Return ${USER_NAME} if the name matches the configured user created via ARGs."""
        if name == production_user and user_created_via_args:
            return "${USER_NAME}"
        return name

    # Track current user context: None = root, string = username or ${USER_NAME}
    # Only inherit explicit parent context - implicit become is added post-processing
    # so child stages start as root (matching the intermediate parent's actual state).
    parent_context = _get_parent_user_context(stage_name, stages_dict, production_user)
    if parent_context is not None:
        current_user = _resolve_user_ref(parent_context)
    else:
        current_user = None

    ordered_steps = []

    for step in steps:
        if _step_is_pip(step) and not venv_active:
            is_root = current_user is None
            venv_step = {"type": "venv_setup", "is_root": is_root}
            if not is_root:
                venv_step["restore_user"] = current_user
            ordered_steps.append(venv_step)
            venv_active = True

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

    return ordered_steps, venv_active


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
    user_name = config.names.user
    has_user = user_name != "root"
    has_explicit_create = has_create_user_in_stages(stages)
    implicit_user = has_user and not has_explicit_create

    if "development" not in stages:
        from container_magic.core.config import StageConfig

        stages["development"] = StageConfig(frm="base", steps=[])

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

    # Leaf stages: not inherited by any other stage.
    # Intermediate stages stay as root so child stages inherit root context.
    inherited_stages = set()
    for sc in stages.values():
        if sc.frm in stages:
            inherited_stages.add(sc.frm)
    leaf_stages = set(stages.keys()) - inherited_stages

    stages_data = []
    venv_state: Dict[str, bool] = {}
    user_created_state: Dict[str, bool] = {}
    for stage_name, stage_config in stages.items():
        base_image = stage_config.frm
        resolved_image = resolve_base_image(base_image, stages)
        from_is_image = ":" in base_image or "/" in base_image

        # Resolve distro: explicit on this stage, or inherited from parent chain
        effective_distro = resolve_inherited_distro(stage_name, stages)
        distro_settings = resolve_distro(effective_distro)
        if distro_settings:
            distro_pm, _, distro_ucs = distro_settings
        else:
            distro_pm, distro_ucs = None, None

        package_manager = (
            stage_config.package_manager
            or distro_pm
            or detect_package_manager(resolved_image)
        )
        user_creation_style = distro_ucs or detect_user_creation_style(resolved_image)

        if from_is_image:
            inherited_venv = False
            inherited_user_created = False
        else:
            inherited_venv = venv_state.get(base_image, False)
            inherited_user_created = user_created_state.get(base_image, False)

        ordered_steps, venv_active = process_stage_steps(
            stage_config,
            stage_name,
            project_dir,
            stages,
            user_name,
            config.names.workspace,
            registry,
            asset_map,
            workspace_symlinks,
            venv_active=inherited_venv,
            implicit_user=implicit_user,
        )
        venv_state[stage_name] = venv_active

        # Inject implicit create_user for from-image stages
        has_explicit_create_in_steps = any(
            s.get("type") == "create_user" for s in ordered_steps
        )
        if has_user and from_is_image and not has_explicit_create_in_steps:
            ordered_steps.insert(0, {"type": "create_user"})
            user_created_state[stage_name] = True
        elif has_explicit_create_in_steps:
            user_created_state[stage_name] = True
        else:
            user_created_state[stage_name] = inherited_user_created

        # Chown venv to runtime user in leaf stages so it's writable in development
        if has_user and stage_name in leaf_stages and venv_active:
            # Determine if we're in a non-root context (inherited from parent)
            last_become_user = None
            for s in reversed(ordered_steps):
                if s.get("type") == "become":
                    last_become_user = s.get("name")
                    break
            inherited_context = _get_parent_user_context(stage_name, stages, user_name)
            is_root = last_become_user is None and inherited_context is None
            chown_step = {"type": "venv_chown", "is_root": is_root}
            if not is_root:
                chown_step["restore_user"] = last_become_user or inherited_context
            ordered_steps.append(chown_step)

        # Inject implicit become at end of leaf stages only
        # Intermediate stages stay as root so child stages inherit root context
        if has_user and stage_name in leaf_stages:
            last_step_is_become = (
                ordered_steps and ordered_steps[-1].get("type") == "become"
            )
            stage_has_user_args = (
                user_created_state.get(stage_name, False)
                or inherited_user_created
                or has_explicit_create_in_steps
                or implicit_user
            )
            become_name = "${USER_NAME}" if stage_has_user_args else user_name
            # Skip if the last step already switches to the same user
            already_correct = (
                last_step_is_become and ordered_steps[-1].get("name") == become_name
            )
            # Also skip if no become steps exist but user context is already set
            # (e.g. explicit become mid-stage followed by non-become steps)
            last_become = None
            for s in reversed(ordered_steps):
                if s.get("type") == "become":
                    last_become = s.get("name")
                    break
            if not already_correct and last_become != become_name:
                ordered_steps.append({"type": "become", "name": become_name})

        ordered_steps = _merge_consecutive_env_steps(ordered_steps)

        needs_user_args = _stage_needs_user_args(ordered_steps)

        stages_data.append(
            {
                "name": stage_name,
                "from": base_image,
                "from_is_image": from_is_image,
                "package_manager": package_manager,
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
