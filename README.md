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

The `run` command works from anywhere in your repository and translates your working directory automatically. When using the `run` alias (not `just run` directly), path translation ensures the container's working directory matches your position in the repository.

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
    standalone: true  # Generate dedicated train.sh script
```

**Development:**
```bash
build
run train  # Use custom command directly (from anywhere)
```

**Production:**
```bash
./build.sh
./run.sh train  # Run via run.sh
./train.sh      # Or use dedicated standalone script
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
    standalone: false  # Default: false (no dedicated script)

  deploy:
    command: bash workspace/deploy.sh
    description: Deploy the model
    standalone: true   # Generates deploy.sh script
```

The `standalone` flag (default: `false`) controls script generation:
- **`standalone: false`** (default) - Command available via `run <command>` and `./run.sh <command>` only
- **`standalone: true`** - Also generates a dedicated `<command>.sh` script for direct execution

**Development:**
- `run train` - from anywhere in your repository
- `just train` - from repository root (if you have `just` installed)

**Production (standalone: false):**
- `./run.sh train` - only way to run

**Production (standalone: true):**
- `./run.sh deploy` - via run.sh
- `./deploy.sh` - dedicated standalone script

### Build Script

Configure the standalone `build.sh` script behaviour:

```yaml
build_script:
  default_target: production  # Optional: default stage to build (default: production)
```

The `build.sh` script can build any defined stage:

```bash
./build.sh              # Builds the default target (production)
./build.sh testing      # Builds the testing stage
./build.sh development  # Builds the development stage
./build.sh --help       # Shows all available targets
```

This is useful when you have multiple build targets beyond just development and production (e.g., testing, staging, or platform-specific builds).

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

**Note:** Both `just` and the `build`/`run` aliases work from anywhere in your project by searching upward for the Justfile/config. For basic development, you only need `just` installed. Installing container-magic is recommended primarily for generating and regenerating files from your YAML config. As a bonus, it also provides command aliases with automatic working directory translation - the `run` alias (not `just run`) adjusts the container's working directory to match your position in the repository, making it feel like you're running commands on the host.

## Using `just` vs `run` Alias

**When calling `just` directly:**
- Paths must be relative to the project root (where the Justfile is)
- Works from anywhere, but you must always specify paths from the project root
- Limitation: `just` changes to the Justfile directory, losing context of where you ran the command

**When using the `run` alias (requires container-magic installed):**
- Automatically translates your working directory to the container
- Paths can be relative to your current location
- The container's working directory matches your position in the repository

**Example:**
```bash
# From project root - both work the same:
just run workspace/script.py  # ✓ Works
run workspace/script.py       # ✓ Works

# Now cd into workspace/ subdirectory:
cd workspace

# just fails because it looks for paths from project root:
just run script.py            # ❌ Fails - looks for script.py in project root (not workspace/)

# run works because it translates your working directory:
run script.py                 # ✓ Works - finds script.py in current dir
```

**Note:** You can make `just` work from subdirectories by always using full paths from the project root (e.g., `just run workspace/script.py` would work from anywhere).

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
├── <command>.sh         # Generated for each command where standalone: true (committed)
├── Justfile             # Generated locally for dev (gitignored)
├── workspace/           # Your code
└── .cm-cache/           # Downloaded assets (gitignored)
```

Command scripts (e.g., `train.sh`, `deploy.sh`) are only generated for commands with `standalone: true` and are committed to the repository.

## Contributing

Container-magic is in early development. Contributions and feedback welcome!
