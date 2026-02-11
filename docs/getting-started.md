# Getting Started

## Installation

```bash
pip install container-magic
```

You'll also need [just](https://github.com/casey/just) installed for the development workflow.

## Create a Project

```bash
# Create from any Docker Hub image
cm init python:3.11 my-project
cd my-project

# Or initialise in the current directory
cm init --here python:3.11

# Use cm.yaml instead of container-magic.yaml
cm init --compact python:3.11 my-project
```

The `<image>` can be any Docker Hub image like `python:3.11`, `ubuntu:22.04`, `pytorch/pytorch`, etc.

## Build and Run

```bash
# Build the container
just build

# Run commands inside the container
just run python --version
just run bash -c "echo Hello from container"
just run  # starts an interactive shell
```

`just` works from anywhere in your project by searching upward for the Justfile.

!!! tip "The `run` alias"
    Container-magic also provides `build` and `run` shell aliases. The `run` alias adds automatic working directory translation — the container's working directory matches your position in the repository:

    ```bash
    cd workspace/src
    run python utils.py        # Works — runs from workspace/src inside the container
    just run python utils.py   # Fails — just always runs from the project root
    ```

## Workflow

```
┌─────────────────────┐
│   cm.yaml           │  ← You edit this
│  (central config)   │
└──────────┬──────────┘
           │
           │  cm init / cm update
           │
           ├─────────────┬──────────────────┬──────────────────┐
           ▼             ▼                  ▼                  ▼
      Dockerfile     Development        Production      Command Scripts
                  ┌───────────────┐  ┌──────────────┐  ┌──────────────┐
                  │ • Justfile    │  │ • build.sh   │  │ • <cmd>.sh   │
                  │               │  │ • run.sh     │  │   (optional) │
                  │ (mounts live  │  │              │  │              │
                  │  workspace)   │  │ (standalone, │  │ (standalone, │
                  └───────────────┘  │  no cm deps) │  │  no cm deps) │
                                     └──────────────┘  └──────────────┘
```

Production files (Dockerfile, build.sh, run.sh, command scripts) are committed to git.
The Justfile is generated locally for developers.

## CLI Commands

```bash
# Create new project
cm init <image> <name>
cm init --here <image>        # Initialise in current dir
cm init --compact <image>     # Use cm.yaml instead of container-magic.yaml

# Regenerate files after editing YAML
cm update

# Development (via Justfile)
just build
just run <command>

# Production (standalone scripts)
./build.sh
./run.sh <command>
```

## Development vs Production

**Development:**

- Workspace mounted from host (edit code live, not baked into image)
- Runs as your user (correct permissions)
- Includes dev dependencies

**Production** (build.sh/run.sh):

- Workspace baked into image
- Standalone scripts (only need docker/podman)
- Minimal dependencies

## Project Structure

```
my-project/
├── cm.yaml              # Your config (committed)
├── Dockerfile           # Generated (committed)
├── build.sh             # Generated (committed)
├── run.sh               # Generated (committed)
├── <command>.sh         # Generated for standalone commands (committed)
├── Justfile             # Generated locally for dev (gitignored)
├── workspace/           # Your code
└── .cm-cache/           # Downloaded assets (gitignored)
```

Command scripts (e.g., `train.sh`, `deploy.sh`) are only generated for commands with `standalone: true`.

## Basic Example

A minimal `cm.yaml`:

```yaml
project:
  name: my-project
  workspace: workspace

stages:
  base:
    from: python:3.11-slim
    packages:
      apt:
        - git
        - build-essential
      pip:
        - numpy
        - pandas

  development:
    from: base

  production:
    from: base
```

## Example with Features

```yaml
project:
  name: ml-training
  workspace: workspace

runtime:
  features:
    - gpu      # NVIDIA GPU
    - display  # X11/Wayland

stages:
  base:
    from: pytorch/pytorch
    packages:
      pip:
        - transformers
        - datasets
    env:
      HF_HOME: /models

  development:
    from: base
    packages:
      pip:
        - pytest
        - ipython

  production:
    from: base

commands:
  train:
    command: python workspace/train.py
    description: Train the model
    standalone: true  # Generate dedicated train.sh script
```

**Development:**

```bash
just build
just train  # Custom commands become just recipes
```

**Production:**

```bash
./build.sh
./run.sh train  # Run via run.sh
./train.sh      # Or use dedicated standalone script
```
