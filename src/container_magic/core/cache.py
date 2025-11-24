"""Cache management for downloaded assets."""

import hashlib
import json
import shutil
import urllib.parse
from pathlib import Path
from typing import List, Tuple

import requests


def get_cache_dir(project_dir: Path) -> Path:
    """Get the cache directory for a project."""
    return project_dir / ".cm-cache" / "assets"


def url_to_hash(url: str) -> str:
    """Convert URL to SHA256 hash for cache directory naming."""
    return hashlib.sha256(url.encode()).hexdigest()


def extract_filename_from_url(url: str) -> str:
    """Extract filename from URL, fallback to 'asset' if not available."""
    parsed = urllib.parse.urlparse(url)
    path = parsed.path
    if path and "/" in path:
        filename = path.split("/")[-1]
        if filename and not filename.startswith("?"):
            return filename
    return "asset"


def get_asset_cache_path(project_dir: Path, url: str) -> Tuple[Path, Path]:
    """
    Get cache paths for an asset.

    Returns:
        (cache_dir, asset_file) tuple
    """
    cache_dir = get_cache_dir(project_dir)
    url_hash = url_to_hash(url)
    asset_dir = cache_dir / url_hash
    filename = extract_filename_from_url(url)
    asset_file = asset_dir / filename

    return asset_dir, asset_file


def get_asset_meta_path(asset_dir: Path) -> Path:
    """Get path to meta.json for an asset."""
    return asset_dir / "meta.json"


def download_asset(url: str, dest_path: Path) -> None:
    """Download asset from URL to destination path."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()

    with open(dest_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)


def cache_asset(project_dir: Path, url: str, container_dest: str) -> Tuple[Path, Path]:
    """
    Download and cache an asset if not already cached.

    Args:
        project_dir: Project directory
        url: URL to download from
        container_dest: Destination path in container

    Returns:
        (asset_dir, asset_file) tuple for cached asset
    """
    asset_dir, asset_file = get_asset_cache_path(project_dir, url)
    meta_path = get_asset_meta_path(asset_dir)

    # Check if already cached
    if asset_file.exists() and meta_path.exists():
        # Verify metadata matches
        with open(meta_path) as f:
            meta = json.load(f)
        if meta.get("url") == url and meta.get("dest") == container_dest:
            return asset_dir, asset_file

    # Download asset
    asset_dir.mkdir(parents=True, exist_ok=True)
    download_asset(url, asset_file)

    # Write metadata
    meta = {"url": url, "dest": container_dest, "filename": asset_file.name}
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    return asset_dir, asset_file


def list_cached_assets(project_dir: Path) -> List[dict]:
    """List all cached assets with their metadata."""
    cache_dir = get_cache_dir(project_dir)
    if not cache_dir.exists():
        return []

    assets = []
    for asset_dir in cache_dir.iterdir():
        if not asset_dir.is_dir():
            continue

        meta_path = get_asset_meta_path(asset_dir)
        if not meta_path.exists():
            continue

        with open(meta_path) as f:
            meta = json.load(f)

        # Get file size
        asset_files = list(asset_dir.glob("*"))
        asset_files = [f for f in asset_files if f.name != "meta.json"]
        size = sum(f.stat().st_size for f in asset_files) if asset_files else 0

        assets.append(
            {
                "url": meta.get("url"),
                "dest": meta.get("dest"),
                "filename": meta.get("filename"),
                "hash": asset_dir.name,
                "size": size,
            }
        )

    return assets


def clear_cache(project_dir: Path) -> None:
    """Clear all cached assets."""
    cache_root = project_dir / ".cm-cache"
    if cache_root.exists():
        shutil.rmtree(cache_root)
