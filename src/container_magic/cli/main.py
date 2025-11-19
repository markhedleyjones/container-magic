"""Main CLI for container-magic."""

import subprocess
import sys
from pathlib import Path

import click

from container_magic import __version__
from container_magic.core.config import ContainerMagicConfig
from container_magic.generators.build_script import generate_build_script
from container_magic.generators.dockerfile import generate_dockerfile
from container_magic.generators.justfile import generate_justfile
from container_magic.generators.run_script import generate_run_script


@click.group()
@click.version_option(version=__version__)
def cli():
    """Container-magic: Rapidly create containerised development environments."""
    pass


@cli.command()
@click.argument("template")
@click.argument("name")
@click.option(
    "--path",
    type=Path,
    help="Directory to create project in (default: current directory)",
)
def init(template: str, name: str, path: Path | None):
    """Initialize a new container-magic project from a template."""
    click.echo(f"Initializing {name} from {template} template...")

    if path is None:
        path = Path.cwd() / name
    else:
        path = path / name

    if path.exists():
        click.echo(f"Error: Directory {path} already exists", err=True)
        sys.exit(1)

    # TODO: Implement template initialization
    click.echo(f"Creating project at {path}")
    path.mkdir(parents=True)

    # Create default config
    config = ContainerMagicConfig(
        project={"name": name, "workspace": "workspace"},
        template={
            "base": f"{template}:latest"
            if template in ["python", "ubuntu", "debian", "alpine"]
            else template
        },
    )

    config_path = path / "container-magic.yaml"
    config.to_yaml(config_path)

    # Create workspace directory
    (path / "workspace").mkdir()

    # Generate Dockerfile, Justfile, and standalone scripts
    generate_dockerfile(config, path / "Dockerfile")
    generate_justfile(config, config_path, path / "Justfile")
    generate_build_script(config, path)
    generate_run_script(config, path)

    # Create .gitignore
    gitignore_content = """# Container-magic generated files are committed
# Add your project-specific ignores below

# Container-magic cache
.cm-cache/
"""
    (path / ".gitignore").write_text(gitignore_content)

    click.echo(f"✓ Created {name}")
    click.echo("Next steps:")
    click.echo(f"  cd {name}")
    click.echo("  cm build")


@cli.command()
@click.option(
    "--path", type=Path, default=Path.cwd(), help="Project directory (default: current)"
)
def update(path: Path):
    """Regenerate all files from container-magic.yaml."""
    config_path = path / "container-magic.yaml"

    if not config_path.exists():
        click.echo(
            "Error: container-magic.yaml not found in current directory", err=True
        )
        sys.exit(1)

    click.echo("Regenerating files from configuration...")

    # Load config
    config = ContainerMagicConfig.from_yaml(config_path)

    # Generate all files
    generate_dockerfile(config, path / "Dockerfile")
    generate_justfile(config, config_path, path / "Justfile")
    generate_build_script(config, path)
    generate_run_script(config, path)

    click.echo("✓ Regenerated successfully")


@cli.command()
@click.option(
    "--path", type=Path, default=Path.cwd(), help="Project directory (default: current)"
)
def generate(path: Path):
    """Regenerate all files from container-magic.yaml (alias for update)."""
    update.callback(path)


@cli.command()
@click.option(
    "--path", type=Path, default=Path.cwd(), help="Project directory (default: current)"
)
def build(path: Path):
    """Build container image (regenerates if config changed)."""
    config_path = path / "container-magic.yaml"

    if not config_path.exists():
        click.echo(
            "Error: container-magic.yaml not found in current directory", err=True
        )
        sys.exit(1)

    # Load config to check for cached assets
    config = ContainerMagicConfig.from_yaml(config_path)

    # Download cached assets if any are defined
    if config.template.cached_assets:
        from container_magic.core.cache import cache_asset

        click.echo("Downloading cached assets...")
        for asset in config.template.cached_assets:
            try:
                asset_dir, asset_file = cache_asset(path, asset.url, asset.dest)
                if asset_file.exists():
                    click.echo(f"  ✓ {asset.url} → {asset_file.relative_to(path)}")
            except Exception as e:
                click.echo(f"  ✗ Failed to download {asset.url}: {e}", err=True)
                sys.exit(1)

    # Check if just is available
    if not subprocess.run(["which", "just"], capture_output=True).returncode == 0:
        click.echo("Error: 'just' command not found. Please install just.", err=True)
        sys.exit(1)

    # Call just build
    result = subprocess.run(["just", "build"], cwd=path)
    sys.exit(result.returncode)


@cli.command()
@click.argument("command", nargs=-1, required=False)
@click.option(
    "--path", type=Path, default=Path.cwd(), help="Project directory (default: current)"
)
def run(command: tuple[str, ...], path: Path):
    """Run a command in the container."""
    config_path = path / "container-magic.yaml"

    if not config_path.exists():
        click.echo(
            "Error: container-magic.yaml not found in current directory", err=True
        )
        sys.exit(1)

    # Check if just is available
    if not subprocess.run(["which", "just"], capture_output=True).returncode == 0:
        click.echo("Error: 'just' command not found. Please install just.", err=True)
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
    config_path = path / "container-magic.yaml"

    if not config_path.exists():
        click.echo(
            "Error: container-magic.yaml not found in current directory", err=True
        )
        sys.exit(1)

    # Check if just is available
    if not subprocess.run(["which", "just"], capture_output=True).returncode == 0:
        click.echo("Error: 'just' command not found. Please install just.", err=True)
        sys.exit(1)

    # Call just shell
    result = subprocess.run(["just", "shell"], cwd=path)
    sys.exit(result.returncode)


def main():
    """Entry point for cm command."""
    cli()


def run_main():
    """Entry point for run command (docker-bbq style)."""
    # TODO: Find nearest container-magic.yaml
    # TODO: Execute command in that project
    if len(sys.argv) == 1:
        click.echo("Usage: run <command> [args...]")
        sys.exit(1)

    click.echo(f"run: {' '.join(sys.argv[1:])}")


if __name__ == "__main__":
    main()
