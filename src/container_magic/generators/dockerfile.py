"""Dockerfile generation from configuration."""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from jinja2 import Environment, PackageLoader, select_autoescape

from container_magic.core.cache import build_asset_map
from container_magic.core.config import (
    ContainerMagicConfig,
    StageConfig,
    UserTargetConfig,
)
from container_magic.core.registry import load_registry
from container_magic.core.steps import parse_step
from container_magic.core.templates import (
    detect_package_manager,
    detect_shell,
    detect_user_creation_style,
    resolve_base_image,
)


def get_user_config(
    config: ContainerMagicConfig, target: str = "production"
) -> Optional[UserTargetConfig]:
    """Get the user configuration for a specific target (development or production), or None if not defined."""

    if config.user:
        if target == "development":
            return config.user.development
        elif target == "production":
            return config.user.production
    return None


def _step_is_become_user(step: Union[str, Dict[str, Any]]) -> bool:
    """Check if a step is a become_user keyword."""
    return isinstance(step, str) and step == "become_user"


def _step_is_become_root(step: Union[str, Dict[str, Any]]) -> bool:
    """Check if a step is a become_root keyword."""
    return isinstance(step, str) and step == "become_root"


def _step_is_create_user(step: Union[str, Dict[str, Any]]) -> bool:
    """Check if a step is a create_user keyword."""
    return isinstance(step, str) and step == "create_user"


def _parent_ends_as_user(
    stage_name: str,
    stages_dict: Dict[str, StageConfig],
) -> bool:
    """Check if the parent stage hierarchy ends with user context active.

    Walks up the stage tree via `frm` references. For each stage, looks at the
    last become_user/become_root step. Returns True if the nearest explicit
    switch is become_user, False otherwise.
    """
    visited: set = set()
    current = stages_dict.get(stage_name)
    if current is None:
        return False

    # Start from the current stage's parent
    parent_name = current.frm
    while parent_name in stages_dict:
        if parent_name in visited:
            break
        visited.add(parent_name)

        parent = stages_dict[parent_name]
        steps = parent.steps

        # If parent has explicit steps, scan for last switch
        if steps is not None:
            last_switch = None
            for step in steps:
                if _step_is_become_user(step):
                    last_switch = "user"
                elif _step_is_become_root(step):
                    last_switch = "root"
            if last_switch is not None:
                return last_switch == "user"

        # No explicit steps - if FROM a Docker image, no user context
        if ":" in parent.frm or "/" in parent.frm:
            return False

        # FROM another stage - keep walking up
        parent_name = parent.frm

    return False


def _has_create_user_in_hierarchy(
    stage_name: str,
    stage: StageConfig,
    stages_dict: Dict[str, StageConfig],
    has_explicit_user_config: bool,
) -> bool:
    """Walk up the stage hierarchy to find if any parent has create_user."""
    if stage.frm not in stages_dict:
        return False

    current_stage_name = stage.frm
    visited = set()

    while current_stage_name in stages_dict:
        if current_stage_name in visited:
            break
        visited.add(current_stage_name)

        current_stage = stages_dict[current_stage_name]
        if current_stage.steps:
            for step in current_stage.steps:
                if _step_is_create_user(step):
                    return True
        # Check if parent uses default build steps (no steps specified and FROM a Docker image)
        if current_stage.steps is None and (
            ":" in current_stage.frm or "/" in current_stage.frm
        ):
            # Default build steps include create_user when user is configured
            if has_explicit_user_config:
                return True

        # Move to parent stage
        if current_stage.frm in stages_dict:
            current_stage_name = current_stage.frm
        else:
            break

    return False


def _stage_needs_user_args(ordered_steps: List[Dict], has_non_root_user: bool) -> bool:
    """Check if a stage's steps require user-related ARGs.

    Returns True if any step references user ARGs (USER_UID, USER_GID, etc.):
    - create_user or become_user steps
    - copy steps with --chown
    - copy_workspace when a non-root user is configured
    """
    for step in ordered_steps:
        if step["type"] in ("create_user", "become_user"):
            return True
        if step["type"] == "copy" and step.get("chown"):
            return True
        if step["type"] == "copy_workspace" and has_non_root_user:
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

    The args string is "source dest" (possibly with extra flags).
    If the first non-flag token matches an asset filename, replace it
    with the cache path.
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
    has_explicit_user_config: bool,
    workspace_name: str,
    registry: Dict = None,
    asset_map: Dict[str, str] = None,
) -> List[Dict]:
    """Process build steps for a stage.

    Handles both v1 (flat string) and v2 (structured dict) step syntax.
    When asset_map is provided, copy sources matching asset filenames are
    rewritten to their cache paths.

    Returns:
        ordered_steps list
    """
    if registry is None:
        registry = load_registry()
    if asset_map is None:
        asset_map = {}

    # Default build order if not specified
    if stage.steps is None:
        if ":" in stage.frm or "/" in stage.frm:
            ordered_steps: List[Dict] = [
                {"type": "system_packages"},
                {"type": "pip_packages"},
            ]
            if has_explicit_user_config:
                ordered_steps.append({"type": "create_user"})
            return ordered_steps
        else:
            steps: List[Union[str, Dict[str, Any]]] = []
            if stage_name == "production":
                steps = ["copy_workspace"]
    else:
        steps = list(stage.steps)

    has_create_user = False
    has_become_user = False

    user_is_active = _parent_ends_as_user(stage_name, stages_dict)

    ordered_steps = []

    for step in steps:
        parsed = parse_step(step, registry)

        step_type = parsed["type"]

        if step_type == "keyword":
            keyword = parsed["keyword"]
            if keyword == "create_user":
                ordered_steps.append({"type": "create_user"})
                has_create_user = True
            elif keyword == "become_user":
                ordered_steps.append({"type": "become_user"})
                has_become_user = True
                user_is_active = True
            elif keyword == "become_root":
                ordered_steps.append({"type": "become_root"})
                user_is_active = False
            elif keyword == "copy_workspace":
                ordered_steps.append({"type": "copy_workspace"})

        elif step_type == "copy_v1":
            chown = parsed["chown"]
            if chown == "context":
                chown = user_is_active
            args = _resolve_copy_source(parsed["args"], asset_map)
            ordered_steps.append({"type": "copy", "args": args, "chown": chown})

        elif step_type == "copy_v2":
            for args in parsed["args_list"]:
                args = _resolve_copy_source(args, asset_map)
                ordered_steps.append(
                    {"type": "copy", "args": args, "chown": user_is_active}
                )

        elif step_type == "env":
            ordered_steps.append({"type": "env", "vars": parsed["vars"]})

        elif step_type == "run":
            command = parsed["command"]
            if "\n" in command and "&& \\" not in command:
                lines = [line for line in command.splitlines() if line.strip()]
                command = " && \\\n    ".join(lines)
            ordered_steps.append({"type": "custom", "command": command})

        elif step_type == "passthrough":
            ordered_steps.append({"type": "custom", "command": parsed["command"]})

    # Validation: Check if become_user used but no create_user in this or parent stages
    if has_become_user and not has_create_user:
        user_created = _has_create_user_in_hierarchy(
            stage_name, stage, stages_dict, has_explicit_user_config
        )
        if not user_created:
            print(
                f"\u26a0\ufe0f  Warning: Stage '{stage_name}' uses 'become_user' but no 'create_user' found in this stage or parent stages",
                file=sys.stderr,
            )
            print("   The become_user step may fail at build time.", file=sys.stderr)

    # Validation: Check if create_user or become_user used but production.user not defined
    if (has_create_user or has_become_user) and not has_explicit_user_config:
        raise ValueError(
            f"Stage '{stage_name}' uses 'create_user' or 'become_user' but production.user is not defined. "
            "Define production.user in your configuration."
        )

    return ordered_steps


def generate_dockerfile(config: ContainerMagicConfig, output_path: Path) -> None:
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

    if "development" not in stages:
        from container_magic.core.config import StageConfig

        stages["development"] = StageConfig(frm="base", steps=["become_user"])

    if "production" not in stages:
        from container_magic.core.config import StageConfig

        stages["production"] = StageConfig(frm="base")

    user_cfg = get_user_config(config)
    registry = load_registry(
        project_overrides=config.command_registry if config.command_registry else None
    )

    # Build asset map from project-level assets
    project_dir = output_path.parent
    asset_map = build_asset_map(project_dir, config.project.assets)

    stages_data = []
    for stage_name, stage_config in stages.items():
        base_image = stage_config.frm
        resolved_image = resolve_base_image(base_image, stages)
        package_manager = stage_config.package_manager or detect_package_manager(
            resolved_image
        )
        shell = stage_config.shell or detect_shell(resolved_image)
        user_creation_style = detect_user_creation_style(resolved_image)

        has_explicit_user = user_cfg is not None
        user_name = user_cfg.name if user_cfg else "root"
        ordered_steps = process_stage_steps(
            stage_config,
            stage_name,
            project_dir,
            stages,
            user_name,
            has_explicit_user,
            config.project.workspace,
            registry,
            asset_map,
        )

        ordered_steps = _merge_consecutive_env_steps(ordered_steps)

        has_non_root_user = user_cfg is not None and user_cfg.name != "root"
        needs_user_args = _stage_needs_user_args(ordered_steps, has_non_root_user)
        from_is_image = ":" in base_image or "/" in base_image

        stages_data.append(
            {
                "name": stage_name,
                "from": base_image,
                "from_is_image": from_is_image,
                "apt_packages": stage_config.packages.apt or [],
                "apk_packages": stage_config.packages.apk or [],
                "dnf_packages": stage_config.packages.dnf or [],
                "pip_packages": stage_config.packages.pip,
                "env_vars": stage_config.env,
                "package_manager": package_manager,
                "shell": shell,
                "user_creation_style": user_creation_style,
                "user": user_name,
                "user_uid": (user_cfg.uid if user_cfg.uid is not None else 1000)
                if user_cfg
                else 0,
                "user_gid": (user_cfg.gid if user_cfg.gid is not None else 1000)
                if user_cfg
                else 0,
                "user_home": (user_cfg.home or f"/home/{user_cfg.name}")
                if user_cfg
                else "/root",
                "ordered_steps": ordered_steps,
                "needs_user_args": needs_user_args,
            }
        )

    dockerfile_content = template.render(
        stages=stages_data,
        workspace_name=config.project.workspace,
    )

    with open(output_path, "w") as f:
        f.write(dockerfile_content)
