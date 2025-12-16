"""Main CLI for container-magic."""

import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

import click

from container_magic import __version__
from container_magic.core.config import ContainerMagicConfig, find_config_file
from container_magic.generators.build_script import generate_build_script
from container_magic.generators.dockerfile import generate_dockerfile
from container_magic.generators.justfile import generate_justfile
from container_magic.generators.run_script import generate_run_script
from container_magic.generators.standalone_commands import (
    generate_standalone_command_scripts,
)


def update_gitignore(path: Path):
    """Update .gitignore with required entries."""
    gitignore_path = path / ".gitignore"
    required_entries = [".cm-cache/", "Justfile"]

    if gitignore_path.exists():
        # Read existing content
        existing_content = gitignore_path.read_text()
        existing_lines = existing_content.split("\n")

        # Check which entries need to be added
        entries_to_add = [
            entry for entry in required_entries if entry not in existing_lines
        ]

        if entries_to_add:
            # Append missing entries
            with gitignore_path.open("a") as f:
                # Ensure file ends with newline before appending
                if existing_content and not existing_content.endswith("\n"):
                    f.write("\n")
                for entry in entries_to_add:
                    f.write(f"{entry}\n")
    else:
        # Create new .gitignore
        gitignore_content = """.cm-cache/
Justfile
"""
        gitignore_path.write_text(gitignore_content)


def _show_just_install_help():
    """Display platform-specific installation instructions for 'just'."""
    click.echo("Error: 'just' command not found", err=True)
    click.echo("", err=True)
    click.echo("'just' is required to run container-magic projects.", err=True)
    click.echo("Install it using one of these methods:", err=True)
    click.echo("", err=True)

    system = platform.system()

    if system == "Linux":
        # Detect Linux distribution
        distro = ""
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("ID="):
                        distro = line.strip().split("=")[1].strip('"')
                        break
        except Exception:
            pass

        if distro in ["arch", "manjaro"]:
            click.echo("  pacman -S just", err=True)
        elif distro in ["ubuntu", "debian", "linuxmint", "pop"]:
            click.echo("  # Using cargo (recommended):", err=True)
            click.echo("  cargo install just", err=True)
            click.echo("", err=True)
            click.echo("  # Or download pre-built binary:", err=True)
            click.echo(
                "  curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to /usr/local/bin",
                err=True,
            )
        elif distro in ["fedora", "rhel", "centos"]:
            click.echo("  dnf install just", err=True)
        else:
            click.echo("  # Using cargo:", err=True)
            click.echo("  cargo install just", err=True)
            click.echo("", err=True)
            click.echo("  # Or download pre-built binary:", err=True)
            click.echo(
                "  curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to /usr/local/bin",
                err=True,
            )
    elif system == "Darwin":  # macOS
        click.echo("  # Using Homebrew (recommended):", err=True)
        click.echo("  brew install just", err=True)
        click.echo("", err=True)
        click.echo("  # Or using cargo:", err=True)
        click.echo("  cargo install just", err=True)
    elif system == "Windows":
        click.echo("  # Using Scoop (recommended):", err=True)
        click.echo("  scoop install just", err=True)
        click.echo("", err=True)
        click.echo("  # Or using Cargo:", err=True)
        click.echo("  cargo install just", err=True)
        click.echo("", err=True)
        click.echo("  # Or using Chocolatey:", err=True)
        click.echo("  choco install just", err=True)
    else:
        click.echo("  # Using cargo:", err=True)
        click.echo("  cargo install just", err=True)

    click.echo("", err=True)
    click.echo("Learn more: https://github.com/casey/just", err=True)


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
    "--compact",
    is_flag=True,
    help="Use compact config (cm.yaml) without comments",
)
@click.option(
    "--here",
    "--in-place",
    "in_place",
    is_flag=True,
    help="Initialize in current directory instead of creating new one",
)
def init(
    template: str,
    name: Optional[str],
    path: Optional[Path],
    compact: bool,
    in_place: bool,
):
    """Initialize a new container-magic project from a template."""
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

    click.echo(f"Initializing {name} from {template} template...")

    # Determine project path
    if in_place:
        # Initialize in current directory
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
        click.echo(f"Initializing in {path}")

    # Create default config with base, development, and production stages
    # If no tag specified, append :latest
    base_image = f"{template}:latest" if ":" not in template else template
    config = ContainerMagicConfig(
        project={
            "name": name,
            "workspace": "workspace",
        },
        user={
            "development": {"host": True},
            "production": {"name": "user"},
        },
        stages={
            "base": {"from": base_image, "steps": ["create_user"]},
            "development": {"from": "base", "steps": ["switch_user"]},
            "production": {"from": "base"},
        },
    )

    # Choose filename based on compact flag
    config_filename = "cm.yaml" if compact else "container-magic.yaml"
    config_path = path / config_filename
    config.to_yaml(config_path, compact=compact)

    # Create workspace directory if it doesn't exist
    workspace_dir = path / "workspace"
    if not workspace_dir.exists():
        workspace_dir.mkdir()
    elif in_place:
        click.echo("  Note: Using existing workspace directory")

    # Generate Dockerfile, Justfile, and standalone scripts
    generate_dockerfile(config, path / "Dockerfile")
    generate_justfile(config, config_path, path / "Justfile")
    generate_build_script(config, path)
    generate_run_script(config, path)
    generate_standalone_command_scripts(config, path)

    # Update .gitignore
    update_gitignore(path)

    click.echo(f"✓ Created {name}")
    click.echo("Next steps:")
    click.echo(f"  cd {name}")
    click.echo("  cm build")


@cli.command()
@click.option(
    "--path", type=Path, default=Path.cwd(), help="Project directory (default: current)"
)
def update(path: Path):
    """Regenerate all files from config (cm.yaml or container-magic.yaml)."""
    config_path = find_config_file(path)

    click.echo("Regenerating files from configuration...")

    # Load config
    config = ContainerMagicConfig.from_yaml(config_path)

    # Generate all files
    generate_dockerfile(config, path / "Dockerfile")
    generate_justfile(config, config_path, path / "Justfile")
    generate_build_script(config, path)
    generate_run_script(config, path)
    generate_standalone_command_scripts(config, path)

    # Update .gitignore
    update_gitignore(path)

    click.echo("✓ Regenerated successfully")


@cli.command()
@click.option(
    "--path", type=Path, default=Path.cwd(), help="Project directory (default: current)"
)
def generate(path: Path):
    """Regenerate all files from config (alias for update)."""
    update.callback(path)


@cli.command()
@click.option(
    "--path", type=Path, default=Path.cwd(), help="Project directory (default: current)"
)
def build(path: Path):
    """Build container image (regenerates if config changed)."""
    config_path = find_config_file(path)

    # Load config to check for cached assets
    config = ContainerMagicConfig.from_yaml(config_path)

    # Download cached assets from all stages
    from container_magic.core.cache import cache_asset

    has_assets = False
    for stage_name, stage_config in config.stages.items():
        if stage_config.cached_assets:
            if not has_assets:
                click.echo("Downloading cached assets...")
                has_assets = True
            for asset in stage_config.cached_assets:
                try:
                    asset_dir, asset_file = cache_asset(path, asset.url, asset.dest)
                    if asset_file.exists():
                        click.echo(
                            f"  ✓ [{stage_name}] {asset.url} → {asset_file.relative_to(path)}"
                        )
                except Exception as e:
                    click.echo(
                        f"  ✗ [{stage_name}] Failed to download {asset.url}: {e}",
                        err=True,
                    )
                    sys.exit(1)

    # Check if just is available
    if not subprocess.run(["which", "just"], capture_output=True).returncode == 0:
        _show_just_install_help()
        sys.exit(1)

    # Call just build
    result = subprocess.run(["just", "build"], cwd=path)
    sys.exit(result.returncode)


@cli.command()
@click.argument("command", nargs=-1, required=False)
@click.option(
    "--path", type=Path, default=Path.cwd(), help="Project directory (default: current)"
)
def run(command: Tuple[str, ...], path: Path):
    """Run a command in the container."""
    find_config_file(path)

    # Check if just is available
    if not subprocess.run(["which", "just"], capture_output=True).returncode == 0:
        _show_just_install_help()
        sys.exit(1)

    # Call just run with command
    just_args = ["just", "run"]
    if command:
        just_args.extend(command)
    result = subprocess.run(just_args, cwd=path)
    sys.exit(result.returncode)


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
        click.echo(f"✓ Cleared cache at {cache_dir}")
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
        click.echo(f"  • {asset['filename']} ({size_mb:.2f} MB)")
        click.echo(f"    URL: {asset['url']}")
        click.echo(f"    Dest: {asset['dest']}")
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
@click.option(
    "--path", type=Path, default=Path.cwd(), help="Project directory (default: current)"
)
def shell(path: Path):
    """Open an interactive shell in the container."""
    find_config_file(path)

    # Check if just is available
    if not subprocess.run(["which", "just"], capture_output=True).returncode == 0:
        _show_just_install_help()
        sys.exit(1)

    # Call just shell
    result = subprocess.run(["just", "shell"], cwd=path)
    sys.exit(result.returncode)


def main():
    """Entry point for cm command."""
    cli()


def run_main():
    """Entry point for run command (standalone alias)."""
    # Find nearest config file by walking up from current directory
    current_dir = Path.cwd()
    project_dir = None

    for parent in [current_dir] + list(current_dir.parents):
        if (parent / "cm.yaml").exists() or (parent / "container-magic.yaml").exists():
            project_dir = parent
            break

    if not project_dir:
        click.echo(
            "Error: No config file (cm.yaml or container-magic.yaml) found in current directory or parents",
            err=True,
        )
        sys.exit(1)

    # Check if just is available
    if not subprocess.run(["which", "just"], capture_output=True).returncode == 0:
        _show_just_install_help()
        sys.exit(1)

    # Load config to check for custom commands
    config_path = find_config_file(project_dir)
    config = ContainerMagicConfig.from_yaml(config_path)

    # Pass user's current working directory to just for path translation
    user_cwd = str(current_dir.resolve())

    # Check if first argument is a custom command
    if len(sys.argv) > 1 and config.commands and sys.argv[1] in config.commands:
        # Call just <command> directly
        just_args = ["just", "--set", "USER_CWD", user_cwd, sys.argv[1]]
        if len(sys.argv) > 2:
            just_args.extend(sys.argv[2:])
    else:
        # Call just run with command
        just_args = ["just", "--set", "USER_CWD", user_cwd, "run"]
        if len(sys.argv) > 1:
            just_args.extend(sys.argv[1:])

    result = subprocess.run(just_args, cwd=project_dir)
    sys.exit(result.returncode)


def build_main():
    """Entry point for build command (standalone alias)."""
    # Find nearest config file by walking up from current directory
    current_dir = Path.cwd()
    project_dir = None

    for parent in [current_dir] + list(current_dir.parents):
        if (parent / "cm.yaml").exists() or (parent / "container-magic.yaml").exists():
            project_dir = parent
            break

    if not project_dir:
        click.echo(
            "Error: No config file (cm.yaml or container-magic.yaml) found in current directory or parents",
            err=True,
        )
        sys.exit(1)

    # Load config
    config_path = find_config_file(project_dir)
    config = ContainerMagicConfig.from_yaml(config_path)

    # Download cached assets from all stages
    from container_magic.core.cache import cache_asset

    has_assets = False
    for stage_name, stage_config in config.stages.items():
        if stage_config.cached_assets:
            if not has_assets:
                click.echo("Downloading cached assets...")
                has_assets = True
            for asset in stage_config.cached_assets:
                try:
                    asset_dir, asset_file = cache_asset(
                        project_dir, asset.url, asset.dest
                    )
                    if asset_file.exists():
                        click.echo(
                            f"  ✓ [{stage_name}] {asset.url} → {asset_file.relative_to(project_dir)}"
                        )
                except Exception as e:
                    click.echo(
                        f"  ✗ [{stage_name}] Failed to download {asset.url}: {e}",
                        err=True,
                    )
                    sys.exit(1)

    # Check if just is available
    if not subprocess.run(["which", "just"], capture_output=True).returncode == 0:
        _show_just_install_help()
        sys.exit(1)

    # Call just build
    result = subprocess.run(["just", "build"], cwd=project_dir)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
