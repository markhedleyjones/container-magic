# Getting Started

## Installation

```bash
pip install container-magic
```

## Create a Project

```bash
# Create from any Docker Hub image
cm init python:3.11 my-project
cd my-project

# Or initialise in the current directory
cm init --here python:3.11
```

The `<image>` can be any Docker Hub image like `python:3.11`, `ubuntu:22.04`, `pytorch/pytorch`, etc.

## Build and Run

```bash
# Build the container
cm build

# Run commands inside the container
cm run python --version
cm run bash -c "echo Hello from container"
cm run           # starts an interactive shell
```

## Project Layout

```
my-project/
  cm.yaml           <- config you edit
  Dockerfile        <- generated
  build.sh          <- generated
  run.sh            <- generated
  workspace/        <- your code and assets (baked into the image)
  outputs/          <- data produced at runtime (mounted, NOT in image)
  cache/            <- data produced at runtime (mounted, NOT in image)
```

Anything under `workspace/` is copied into the production image at build time,
so keep it to code, configuration, and small assets. Anything you want to
persist across runs but keep out of the image - model outputs, logs,
downloaded datasets, caches - goes in a sibling folder and is declared under
`runtime.volumes:`.

```yaml
runtime:
  volumes:
    - outputs                  # sibling folder -> /data/outputs
    - cache                    # sibling folder -> /data/cache
    - ../shared                # parent dir, shared with other projects
    - /srv/pipeline/datasets   # absolute path
    - ~/models                 # path under your home
```

Any volume without a colon is shorthand: the container-side path is picked as
`/data/<basename>` from the host path. Relative paths (bare names, `./`, `../`)
are created if missing and anchored to the project directory in development or
to the directory containing `run.sh` in production. Absolute and `~` paths are
passed through as-is and must already exist. Use the full `host:container` form
only when you want a different container name or need mount options like `:ro`.

See [Volumes](configuration.md#volumes) for the full syntax.

## Workflow

```
+---------------------+
|   cm.yaml           |  <- You edit this
|  (central config)   |
+----------+----------+
           |
           |  cm init / cm update
           |
           +-------------+-----------------+
           |             |                 |
      Dockerfile     Development       Production
                  +---------------+  +--------------+
                  | cm build      |  | build.sh     |
                  | cm run        |  | run.sh       |
                  |               |  |              |
                  | (mounts live  |  | (standalone, |
                  |  workspace)   |  |  no cm deps) |
                  +---------------+  +--------------+
```

Production files (Dockerfile, build.sh, run.sh) are committed to git.

## CLI Commands

```bash
# Create new project
cm init <image> <name>
cm init --here <image>        # Initialise in current dir

# Regenerate files after editing YAML
cm update

# Build and run (development)
cm build                      # Build development image
cm build production           # Build production image
cm build testing              # Build any Dockerfile stage
cm build production --tag v1.0  # Build with custom tag
cm run <command>              # Run command in container
cm run                        # Interactive shell

# Stop and clean
cm stop                       # Stop the development container
cm clean                      # Stop container and remove images

# Cache management
cm cache list                 # List cached assets with size and URL
cm cache path                 # Show cache directory location
cm cache clear                # Clear all cached assets
```

### Runtime flag passthrough

Pass arbitrary flags to docker/podman using `--`:

```bash
cm run -e DEBUG=1 -v /data:/data -- my-command
./run.sh -e API_KEY=secret -- my-command
```

### Production (standalone scripts)

```bash
./build.sh                    # Build production image
./build.sh --tag v1.0         # Build with custom tag
./run.sh <command>            # Run command in container
```

## Development vs Production

Container-magic supports two workflows:

!!! tip "How the workspace is handled"

    === "Development"

        The workspace directory is **bind-mounted** from your host. Edit code
        locally and run it in the container immediately - no rebuild needed.
        The container runs as your host user for correct file permissions.

    === "Production"

        The workspace is **baked into the image** via `copy: workspace`.
        Standalone scripts (`build.sh`, `run.sh`) need only docker/podman
        installed - no container-magic dependency.

## Project Structure

```
my-project/
+-- cm.yaml              # Your config (committed)
+-- Dockerfile           # Generated (committed)
+-- build.sh             # Generated (committed)
+-- run.sh               # Generated (committed)
+-- workspace/           # Your code
+-- .env                 # Environment variables for the container (optional)
+-- .cm-cache/           # Build cache (gitignored)
    +-- assets/          # Downloaded assets
    +-- staging/         # Resolved symlinks for build (temporary)
```

## Basic Example

A minimal `cm.yaml`:

```yaml
names:
  image: my-project
  user: nonroot

stages:
  base:
    from: python:3.11-slim
    steps:
      - apt-get:
          install:
            - git
            - build-essential
      - pip:
          install:
            - numpy
            - pandas

  development:
    from: base

  production:
    from: base
```

## Example with Features

```yaml
names:
  image: ml-training
  user: nonroot

runtime:
  features:
    - gpu      # NVIDIA GPU
    - display  # X11/Wayland

stages:
  base:
    from: pytorch/pytorch
    steps:
      - pip:
          install:
            - transformers
            - datasets
      - env:
          HF_HOME: /models

  development:
    from: base
    steps:
      - pip:
          install:
            - pytest
            - ipython

  production:
    from: base

commands:
  train:
    command: python workspace/train.py
    description: Train the model
```

**Development:**

```bash
cm build
cm run train  # Custom commands work via cm run
```

**Production:**

```bash
./build.sh
./run.sh train  # Run via run.sh
```
