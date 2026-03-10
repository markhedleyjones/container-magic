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

!!! tip "The `run` and `build` aliases"
    Container-magic also provides standalone `build` and `run` shell aliases. The `run` alias adds automatic working directory translation - the container's working directory matches your position in the repository:

    ```bash
    cd workspace/src
    run python utils.py   # Works - runs from workspace/src inside the container
    ```

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
cm build --production         # Build production image
cm build --tag v1.0           # Build with custom tag
cm run <command>              # Run command in container
cm run                        # Interactive shell

# Cache management
cm cache list                 # List cached assets with size and URL
cm cache path                 # Show cache directory location
cm cache clear                # Clear all cached assets
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
+-- .cm-cache/           # Downloaded assets (gitignored)
+-- .cm-build-staging/   # Resolved symlinks for build (gitignored, temporary)
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
      - create: user
      - become: user

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
      - create: user
      - become: user

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
