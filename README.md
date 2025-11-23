# container-magic

A tool for rapidly creating containerised development environments. Configure once in YAML, use anywhere with Docker or Podman.

## What It Does

Container-magic takes a single YAML configuration file and generates:
1. A **Dockerfile** with multi-stage builds
2. A **Justfile** for development (with live workspace mounting)
3. Standalone **build.sh** and **run.sh** scripts for production

The Dockerfile and standalone scripts are committed to your repository, so anyone can use your project with just `docker` or `podman` - no need to install container-magic or just.

## Key Features

* **YAML configuration** - Single source of truth for your container setup
* **Transparent execution** - Run commands in container from anywhere in your repo with path translation
* **Custom commands** - Define commands once, use in both dev and prod
* **Smart features** - GPU, display (X11/Wayland), and audio support
* **Multi-stage builds** - Separate base, development, and production stages
* **Live workspace mounting** - Edit code on host, run in container (development)
* **Standalone scripts** - Production needs only docker/podman (no dependencies)

## Quick Start

```bash
# Install
pip install container-magic

# Create a new project
cm init python my-project
cd my-project

# Build the container
build

# Run commands inside the container
run python --version
run bash -c "echo Hello from container"
run  # starts an interactive shell
```

The `run` command works from anywhere in your repository and translates paths automatically, so it feels like running on your host machine.

## Workflow

```
┌─────────────────────┐
│   cm.yaml           │  ← You edit this
│  (central config)   │
└──────────┬──────────┘
           │
           │  cm init / cm update
           │
           ├─────────────┬──────────────────┐
           ▼             ▼                  ▼
      Dockerfile     Development        Production
                  ┌───────────────┐  ┌──────────────┐
                  │ • Justfile    │  │ • build.sh   │
                  │               │  │ • run.sh     │
                  │ (mounts live  │  │              │
                  │  workspace)   │  │ (standalone, │
                  └───────────────┘  │  no cm deps) │
                                     └──────────────┘
```

Production files (Dockerfile, build.sh, run.sh) are committed to git.
The Justfile is generated locally for developers.

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
      apt: [git, build-essential]
      pip: [numpy, pandas]

  development:
    from: base

  production:
    from: base
```

This generates everything you need to build and run your project.

## Example with Features

```yaml
project:
  name: ml-training
  workspace: workspace
  auto_update: true

runtime:
  features:
    - gpu      # NVIDIA GPU
    - display  # X11/Wayland

stages:
  base:
    from: pytorch/pytorch
    packages:
      pip: [transformers, datasets]
    env:
      HF_HOME: /models

  development:
    from: base
    packages:
      pip: [pytest, ipython]

  production:
    from: base

commands:
  train:
    command: python workspace/train.py
    description: Train the model
```

Development:
```bash
build
run train  # Use custom command directly
```

Production:
```bash
./build.sh
./run.sh train     # Run custom command
./run.sh           # Interactive shell
```

## YAML Reference

### Project

```yaml
project:
  name: my-project      # Required: image name
  workspace: workspace  # Required: directory with your code
  auto_update: true     # Optional: auto-regenerate on config changes
```

### Runtime

```yaml
runtime:
  backend: auto      # docker, podman, or auto
  privileged: false  # privileged mode
  features:
    - gpu            # NVIDIA GPU
    - display        # X11/Wayland
    - audio          # PulseAudio/PipeWire
```

### Stages

```yaml
stages:
  base:
    from: python:3.11-slim    # Any Docker Hub image
    packages:
      apt: [git, curl]
      pip: [numpy, pandas]
    env:
      VAR: value

  development:
    from: base                # Inherit from base
    packages:
      pip: [pytest]

  production:
    from: base
```

You can use any image from Docker Hub as your base (e.g., `python:3.11`, `ubuntu:22.04`, `pytorch/pytorch`, `nvidia/cuda:12.4.0-runtime-ubuntu22.04`).

### Commands

Define custom commands that work in both dev and prod:

```yaml
commands:
  train:
    command: python workspace/train.py
    description: Train model
    env:
      CUDA_VISIBLE_DEVICES: "0"
    standalone: true  # Optional: generate train.sh script
```

**Development:**
- `run train` - from anywhere in your repository
- `just train` - from repository root

**Production:**
- `./run.sh train`

If `standalone: true`, also generates `./train.sh` for direct execution.

## CLI Commands

```bash
# Create new project
cm init <image> <name>
cm init --here <image>        # Initialize in current dir
cm init --compact <image>     # Use cm.yaml instead of container-magic.yaml

# Regenerate files after editing YAML
cm update

# Development (aliases)
build
run <command>

# Production (standalone scripts)
./build.sh
./run.sh <command>
./run.sh <custom-command>
```

The `<image>` can be any Docker Hub image like `python:3.11`, `ubuntu:22.04`, `pytorch/pytorch`, etc.

**Note:** Container-magic generates a Justfile that contains the build and run logic. If you have `just` installed, you can also use `just build`, `just run <command>`, and `just <custom-command>` (e.g., `just train`).

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
├── Justfile             # Generated locally for dev (gitignored)
├── workspace/           # Your code
└── .cm-cache/           # Downloaded assets (gitignored)
```

## Contributing

Container-magic is in early development. Contributions and feedback welcome!
