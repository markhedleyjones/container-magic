# container-magic

A tool for rapidly creating containerised development environments. Configure once in YAML, use anywhere with Docker or Podman.

An iteration on the [docker-bbq](https://github.com/markhedleyjones/docker-bbq) project with improved YAML configuration, Python-based tooling, and better dev/prod workflows.

## What It Does

Container-magic takes a single YAML configuration file and generates:
1. A **Dockerfile** with multi-stage builds
2. A **Justfile** for development (with live workspace mounting)
3. Standalone **build.sh** and **run.sh** scripts for production

The generated files are committed to your repository, so anyone can use your project with just `docker`/`podman` and `just` - no need to install container-magic itself.

## Key Features

* **YAML configuration** - Single source of truth for your container setup
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

# Build and run
just build
just run python workspace/script.py
```

## Workflow

```
┌─────────────────────┐
│   cm.yaml           │  ← You edit this
│  (your config)      │
└──────────┬──────────┘
           │
           │  cm init / cm update
           │
           ├─────────────────────────────┐
           ▼                             ▼
  ┌─────────────────┐         ┌──────────────────┐
  │  Development    │         │   Production     │
  ├─────────────────┤         ├──────────────────┤
  │ • Justfile      │         │ • build.sh       │
  │ • just build    │         │ • run.sh         │
  │ • just run      │         │                  │
  │ • just shell    │         │ (standalone,     │
  │                 │         │  no deps)        │
  │ (mounts code)   │         └──────────────────┘
  └─────────────────┘
           │
           └── Both use same Dockerfile
```

All generated files (Dockerfile, Justfile, build.sh, run.sh) are committed to git.

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

Then use:
```bash
just build
just train        # Runs with GPU support
just shell        # Interactive shell
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
```

Use with `just train` or `./run.sh train`.

## CLI Commands

```bash
# Create new project
cm init <image> <name>
cm init --here <image>        # Initialize in current dir
cm init --compact <image>     # Use cm.yaml instead of container-magic.yaml

# Regenerate files after editing YAML
cm update
cmupdate                      # Alias

# Development (uses Justfile)
just build                    # Build dev image
just run <command>            # Run command in container
just shell                    # Interactive shell
just <custom-command>         # Run custom command

# Production (standalone scripts)
./build.sh                    # Build prod image
./run.sh <command>            # Run command
./run.sh <custom-command>     # Run custom command
```

The `<image>` can be any Docker Hub image like `python:3.11`, `ubuntu:22.04`, `pytorch/pytorch`, etc.

## Development vs Production

**Development** (Justfile):
- Workspace mounted from host (edit code live)
- Runs as your user (correct permissions)
- Includes dev dependencies

**Production** (build.sh/run.sh):
- Workspace baked into image
- Standalone scripts (only need docker/podman)
- Minimal dependencies

## Project Structure

```
my-project/
├── cm.yaml              # Your config
├── Dockerfile           # Generated
├── Justfile             # Generated (dev)
├── build.sh             # Generated (prod)
├── run.sh               # Generated (prod)
├── workspace/           # Your code
└── .cm-cache/           # Downloaded assets (gitignored)
```

## Contributing

Container-magic is in early development. Contributions and feedback welcome!
