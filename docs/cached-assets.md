# Cached Assets

Container-magic supports downloading external resources (files, models, datasets) and caching them locally to avoid re-downloading on subsequent builds. Use the `copy_cached_assets` [build step](build-steps.md#6-copy_cached_assets) to include cached assets in your image.

**Use cases:**

- Machine learning models from HuggingFace or other sources
- Large datasets
- Pre-compiled binaries or libraries
- Configuration files from remote sources

## Configuration

Define assets under `cached_assets` in any stage:

```yaml
stages:
  base:
    from: python:3.11-slim
    cached_assets:
      - url: https://example.com/model.tar.gz
        dest: /models/model.tar.gz
      - url: https://huggingface.co/bert-base-uncased/resolve/main/model.safetensors
        dest: /models/bert.safetensors
    steps:
      - copy_cached_assets
```

**Options:**

| Option | Required | Description |
|--------|----------|-------------|
| `url` | Yes | HTTP(S) URL to download from |
| `dest` | Yes | Destination path inside container |

## How It Works

1. Run `cm update` or `cm build` — assets are downloaded (if not cached) with 60-second timeout
2. Files cached in `.cm-cache/assets/<url-hash>/` with `meta.json` metadata
3. Add `copy_cached_assets` to your stage's `steps` to copy into image
4. Subsequent builds reuse cached files, skipping downloads

!!! warning
    If you define `cached_assets` but don't add `copy_cached_assets` to your steps, the assets will be downloaded but not included in the image.

## Cache Management

```bash
cm cache list    # List cached assets with size and URL
cm cache path    # Show cache directory location
cm cache clear   # Clear all cached assets
```

## Example: ML Model in Production Image

```yaml
project:
  name: ml-service

user:
  production:
    name: appuser

stages:
  base:
    from: pytorch/pytorch:latest
    packages:
      pip:
        - transformers
        - flask
    cached_assets:
      - url: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/main/pytorch_model.bin
        dest: /models/model.bin
    steps:
      - install_pip_packages
      - copy_cached_assets

  production:
    from: base
    steps:
      - create_user
      - become_user
      - copy app /app
```

## Multi-stage Downloading

All stages with `cached_assets` download when running `cm build`:

```yaml
stages:
  base:
    cached_assets:
      - url: https://example.com/base-asset.tar.gz
        dest: /opt/base-asset.tar.gz
    steps:
      - copy_cached_assets

  development:
    from: base
    cached_assets:
      - url: https://example.com/dev-asset.zip
        dest: /opt/dev-asset.zip
    steps:
      - copy_cached_assets

  production:
    from: base
    cached_assets:
      - url: https://example.com/prod-asset.tar.gz
        dest: /opt/prod-asset.tar.gz
    steps:
      - copy_cached_assets
```

All three assets are downloaded and available for their respective stages.
