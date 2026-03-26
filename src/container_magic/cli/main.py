"""Main CLI for container-magic."""

import os
import sys
from pathlib import Path
from typing import Optional

import click

from container_magic import __version__
from container_magic.core.config import ContainerMagicConfig, find_config_file
from container_magic.generators.build_script import generate_build_script
from container_magic.generators.dockerfile import generate_dockerfile
from container_magic.generators.run_script import generate_run_script


def _ensure_ignore_entries(path: Path, filename: str, required_entries: list):
    """Ensure an ignore file contains the required entries."""
    ignore_path = path / filename

    if ignore_path.exists():
        existing_content = ignore_path.read_text()
        existing_lines = existing_content.split("\n")

        entries_to_add = [
            entry for entry in required_entries if entry not in existing_lines
        ]

        if entries_to_add:
            with ignore_path.open("a") as f:
                if existing_content and not existing_content.endswith("\n"):
                    f.write("\n")
                for entry in entries_to_add:
                    f.write(f"{entry}\n")
    else:
        ignore_path.write_text("".join(f"{entry}\n" for entry in required_entries))


def update_gitignore(path: Path):
    """Update .gitignore with required entries."""
    _ensure_ignore_entries(path, ".gitignore", [".cm-cache/"])


def update_dockerignore(path: Path):
    """Update .dockerignore to not exclude .cm-cache/.

    Checks if .cm-cache/ is excluded and adds a negation so assets and
    staging files remain accessible in the Docker build context.
    """
    dockerignore_path = path / ".dockerignore"
    if not dockerignore_path.exists():
        return

    content = dockerignore_path.read_text()
    lines = content.split("\n")

    has_cm_cache_exclude = ".cm-cache/" in lines or ".cm-cache" in lines
    has_negation = "!.cm-cache/" in lines or "!.cm-cache" in lines

    if has_cm_cache_exclude and not has_negation:
        with dockerignore_path.open("a") as f:
            if content and not content.endswith("\n"):
                f.write("\n")
            f.write("!.cm-cache/\n")


def _find_project_dir() -> Path:
    """Find the nearest project directory by walking up from cwd."""
    current_dir = Path.cwd()
    for parent in [current_dir] + list(current_dir.parents):
        if (parent / "cm.yaml").exists():
            return parent
    click.echo(
        "Error: No config file (cm.yaml) found in current directory or parents",
        err=True,
    )
    sys.exit(1)


@click.group()
@click.version_option(version=__version__)
def cli():
    """Container-magic: Rapidly create containerised development environments."""
    pass


@cli.command()
@click.argument("template")
@click.argument("name", required=False)
@click.option(
    "--path",
    type=Path,
    help="Directory to create project in (default: current directory)",
)
@click.option(
    "--here",
    "--in-place",
    "in_place",
    is_flag=True,
    help="Initialise in current directory instead of creating new one",
)
def init(
    template: str,
    name: Optional[str],
    path: Optional[Path],
    in_place: bool,
):
    """Initialise a new container-magic project from a template."""
    # Determine project name
    if name is None:
        if in_place:
            # Use current directory name as project name
            name = Path.cwd().name
        else:
            click.echo(
                "Error: name argument is required unless using --here/--in-place",
                err=True,
            )
            sys.exit(1)

    click.echo(f"Initialising {name} from {template} template...")

    # Determine project path
    if in_place:
        # Initialise in current directory
        path = Path.cwd()
    elif path is None:
        # Create new directory with project name
        path = Path.cwd() / name
    else:
        # Create new directory under specified path
        path = path / name

    # Check if directory exists (only for new directory creation)
    if not in_place and path.exists():
        click.echo(f"Error: Directory {path} already exists", err=True)
        sys.exit(1)

    # Create directory if needed
    if not in_place:
        click.echo(f"Creating project at {path}")
        path.mkdir(parents=True)
    else:
        click.echo(f"Initialising in {path}")

    # Create default config with base, development, and production stages
    # If no tag specified, append :latest
    base_image = f"{template}:latest" if ":" not in template else template

    config = ContainerMagicConfig(
        names={"image": name, "workspace": "workspace", "user": "nonroot"},
        stages={
            "base": {"from": base_image},
            "development": {"from": "base"},
            "production": {
                "from": "base",
                "steps": [{"copy": "workspace"}],
            },
        },
    )

    config_path = path / "cm.yaml"
    config.to_yaml(config_path)

    # Create workspace directory if it doesn't exist
    workspace_dir = path / "workspace"
    if not workspace_dir.exists():
        workspace_dir.mkdir()
    elif in_place:
        click.echo("  Note: Using existing workspace directory")

    # Scan workspace symlinks once for all generators
    from container_magic.core.symlinks import scan_workspace_symlinks

    workspace_symlinks = scan_workspace_symlinks(path / config.names.workspace)

    # Generate Dockerfile and production scripts
    generate_dockerfile(
        config, path / "Dockerfile", workspace_symlinks=workspace_symlinks
    )
    generate_build_script(config, path, workspace_symlinks=workspace_symlinks)
    generate_run_script(config, path)

    # Update ignore files
    update_gitignore(path)
    update_dockerignore(path)

    # Warn about leftover Justfile from v2 (only if it was generated by container-magic)
    justfile_path = path / "Justfile"
    if justfile_path.exists():
        try:
            header = justfile_path.read_text()[:200]
            if "Generated by container-magic" in header:
                click.echo(
                    "Warning: Found container-magic generated Justfile from a previous version. "
                    "Justfile is no longer generated. You can safely delete it.",
                    err=True,
                )
        except OSError:
            pass

    click.echo(f"Created {name}")
    click.echo("Next steps:")
    click.echo(f"  cd {name}")
    click.echo("  cm build")


@cli.command()
@click.option(
    "--path", type=Path, default=Path.cwd(), help="Project directory (default: current)"
)
def update(path: Path):
    """Regenerate all files from config (cm.yaml)."""
    config_path = find_config_file(path)

    click.echo("Regenerating files from configuration...")

    # Load config
    config = ContainerMagicConfig.from_yaml(config_path)

    # Scan workspace symlinks once for all generators
    from container_magic.core.symlinks import scan_workspace_symlinks

    workspace_symlinks = scan_workspace_symlinks(path / config.names.workspace)

    # Generate Dockerfile and production scripts
    generate_dockerfile(
        config, path / "Dockerfile", workspace_symlinks=workspace_symlinks
    )
    generate_build_script(config, path, workspace_symlinks=workspace_symlinks)
    generate_run_script(config, path)

    # Update ignore files
    update_gitignore(path)
    update_dockerignore(path)

    # Warn about leftover Justfile from v2 (only if it was generated by container-magic)
    justfile_path = path / "Justfile"
    if justfile_path.exists():
        try:
            header = justfile_path.read_text()[:200]
            if "Generated by container-magic" in header:
                click.echo(
                    "Warning: Found container-magic generated Justfile from a previous version. "
                    "Justfile is no longer generated. You can safely delete it.",
                    err=True,
                )
        except OSError:
            pass

    # Warn about leftover standalone scripts
    if config.commands:
        for cmd_name in config.commands:
            script_path = path / f"{cmd_name}.sh"
            if script_path.exists():
                click.echo(
                    f"Warning: Found standalone script {cmd_name}.sh which is "
                    "no longer generated. You can safely delete it.",
                    err=True,
                )

    click.echo("Regenerated successfully")


def _download_assets(config: ContainerMagicConfig, project_dir: Path):
    """Download all project-level assets."""
    from container_magic.core.cache import cache_asset

    has_assets = False

    for item in config.assets:
        if not has_assets:
            click.echo("Downloading assets...")
            has_assets = True
        try:
            asset_dir, asset_file = cache_asset(project_dir, item.url)
            if asset_file.exists():
                click.echo(
                    f"  {item.filename} -> {asset_file.relative_to(project_dir)}"
                )
        except Exception as e:
            click.echo(f"  Failed to download {item.url}: {e}", err=True)
            sys.exit(1)


@cli.group()
def cache():
    """Manage cached assets."""
    pass


@cache.command("clear")
@click.option(
    "--path", type=Path, default=Path.cwd(), help="Project directory (default: current)"
)
def cache_clear(path: Path):
    """Clear all cached assets."""
    from container_magic.core.cache import clear_cache, get_cache_dir

    cache_dir = get_cache_dir(path)
    if cache_dir.exists():
        clear_cache(path)
        click.echo(f"Cleared cache at {cache_dir}")
    else:
        click.echo("No cache found")


@cache.command("list")
@click.option(
    "--path", type=Path, default=Path.cwd(), help="Project directory (default: current)"
)
def cache_list(path: Path):
    """List all cached assets."""
    from container_magic.core.cache import list_cached_assets

    assets = list_cached_assets(path)
    if not assets:
        click.echo("No cached assets found")
        return

    click.echo(f"Cached assets ({len(assets)}):")
    for asset in assets:
        size_mb = asset["size"] / (1024 * 1024)
        click.echo(f"  {asset['filename']} ({size_mb:.2f} MB)")
        click.echo(f"    URL: {asset['url']}")
        click.echo(f"    Hash: {asset['hash'][:16]}...")


@cache.command("path")
@click.option(
    "--path", type=Path, default=Path.cwd(), help="Project directory (default: current)"
)
def cache_path(path: Path):
    """Show cache directory path."""
    from container_magic.core.cache import get_cache_dir

    cache_dir = get_cache_dir(path)
    click.echo(str(cache_dir))


@cli.command()
def stop():
    """Stop the running development container."""
    from container_magic.core.runner import stop_container

    project_dir = _find_project_dir()
    config_path = find_config_file(project_dir)
    config = ContainerMagicConfig.from_yaml(config_path)
    stop_container(config)


@cli.command()
def clean():
    """Stop container and remove images."""
    from container_magic.core.runner import clean_images, stop_container

    project_dir = _find_project_dir()
    config_path = find_config_file(project_dir)
    config = ContainerMagicConfig.from_yaml(config_path)
    stop_container(config)
    clean_images(config)


@cli.command(
    "run",
    context_settings=dict(
        ignore_unknown_options=True,
        allow_extra_args=True,
        help_option_names=[],
    ),
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def cli_run(args):
    """Run a command in the development container."""
    from container_magic.core.runner import run_container

    project_dir = _find_project_dir()
    user_cwd = Path.cwd()
    config_path = find_config_file(project_dir)
    config = ContainerMagicConfig.from_yaml(config_path)

    os.chdir(project_dir)
    exit_code = run_container(
        config=config,
        project_dir=project_dir,
        user_cwd=user_cwd,
        user_args=list(args),
    )
    sys.exit(exit_code)


@cli.command("build")
@click.argument("target", default="development")
@click.option("--tag", default="", help="Override image tag")
def cli_build(target, tag):
    """Build the container image.

    TARGET is the Dockerfile stage to build (default: development).
    """
    from container_magic.core.builder import build_container

    project_dir = _find_project_dir()
    config_path = find_config_file(project_dir)
    config = ContainerMagicConfig.from_yaml(config_path)

    _download_assets(config, project_dir)

    os.chdir(project_dir)
    exit_code = build_container(
        config=config,
        project_dir=project_dir,
        target=target,
        tag=tag,
    )
    sys.exit(exit_code)


def main():
    """Entry point for cm command."""
    cli()


if __name__ == "__main__":
    main()
