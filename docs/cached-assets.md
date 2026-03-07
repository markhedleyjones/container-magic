# Cached Assets

Container-magic can download external resources (files, models, datasets) and cache them locally to avoid re-downloading on every build. Assets are defined under `project.assets` and copied into the image using `copy:` steps.

**Use cases:**

- Machine learning models from HuggingFace or other sources
- Large datasets
- Pre-compiled binaries or libraries
- Configuration files from remote sources

## Configuration

Define assets under `project.assets`:

```yaml
project:
  name: my-project
  assets:
    - https://example.com/model.tar.gz
    - my-model.bin: https://huggingface.co/bert-base/resolve/main/model.safetensors
```

Each asset can be either:

- A bare URL -- the filename is derived from the URL path
- A `filename: url` mapping -- you choose the local filename

Then use `copy:` steps to place them in the image:

```yaml
stages:
  base:
    from: python:3-slim
    steps:
      - copy: model.tar.gz /models/model.tar.gz
      - copy: my-model.bin /models/bert.safetensors
```

## How It Works

1. Run `cm update` or `cm build` -- assets are downloaded (if not cached)
2. Files cached in `.cm-cache/assets/<hash>/` with metadata
3. Use `copy:` steps to place cached files into the image
4. Subsequent builds reuse cached files, skipping downloads

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
  assets:
    - model.bin: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/main/pytorch_model.bin

user:
  production:
    name: appuser

stages:
  base:
    from: pytorch/pytorch:latest
    steps:
      - pip: {install: [transformers, flask]}
      - create_user
      - become_user
      - copy: model.bin /models/model.bin

  production:
    from: base
    steps:
      - copy app /app
```

## Multiple Assets

```yaml
project:
  name: ml-pipeline
  assets:
    - tokenizer.json: https://example.com/tokenizer.json
    - model.safetensors: https://example.com/model.safetensors
    - config.json: https://example.com/config.json

stages:
  base:
    from: pytorch/pytorch:latest
    steps:
      - create_user
      - become_user
      - copy:
          - tokenizer.json /models/tokenizer.json
          - model.safetensors /models/model.safetensors
          - config.json /models/config.json
```

The `copy:` step accepts a list to copy multiple files. Each item follows the same `source dest` format.
