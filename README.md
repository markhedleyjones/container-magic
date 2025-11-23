# container-magic

A tool for rapidly creating containerised development environments with a focus on simplicity and portability. Configure once in YAML, use anywhere with Docker or Podman.

This tool might be useful if you:
1. Want consistent, reproducible development environments across projects
2. Are tired of manually writing Dockerfiles and docker run commands
3. Work across multiple container-based repositories and want a unified workflow
4. Need smart handling of display (X11/Wayland), GPU, and workspace mounting

## Features

* **YAML-driven configuration** - Single source of truth for your entire container setup
* **Custom commands** - Define reusable commands that work in both development and production
* **Smart `run` command** - Seamlessly execute code in containers with automatic workspace mounting, GPU, and display support
* **Generated artifacts** - Produces Dockerfile, Justfile, and standalone scripts that work without container-magic installed
* **Template system** - Start new projects instantly with proven templates (Python, Ubuntu, Debian, PyTorch, etc.)
* **Docker and Podman support** - Automatically detects and works with either container runtime
* **Multi-stage builds** - Separate base, development, and production stages
* **Standalone production scripts** - Generated `build.sh` and `run.sh` work with no dependencies
* **Auto-update detection** - Warns when config changes and can auto-regenerate files

## Quick Start

### Installation

```bash
pip install container-magic
```

This installs the `cm` command (or `cmupdate` alias).

### Create a New Project

```bash
# Initialize from template
cm init --here python
# or
cm init python my-analytics-project
cd my-analytics-project

# Build and run
just build
just run python analyze.py
```

### Clone an Existing Project

Projects using container-magic work without installing it:

```bash
git clone https://github.com/user/awesome-project
cd awesome-project

# Just works (Dockerfile and Justfile are committed)
just build
just run python main.py
```

## How It Works

Container-magic uses YAML as the single source of truth and generates four files:

1. **Dockerfile** - Multi-stage build with all your dependencies
2. **Justfile** - Task definitions for development workflow
3. **build.sh** - Standalone production build script
4. **run.sh** - Standalone production run script

These generated files are **committed to git**, making your project usable by anyone with `docker`/`podman` installed, even without container-magic.

### Basic Workflow

```
cm.yaml or               ──┐
container-magic.yaml       │
  (source of truth)        │
                           ├─> cm init/update
                           │
                           ├─> Dockerfile (generated)
                           ├─> Justfile (generated, for development)
                           │   ├─> just build
                           │   ├─> just run
                           │   └─> just shell
                           │
                           ├─> build.sh (generated, for production)
                           └─> run.sh (generated, for production)
```

## Configuration

### Complete Example

```yaml
project:
  name: my-project
  workspace: workspace
  auto_update: true  # Auto-regenerate when config changes
  production_user:
    name: appuser
    uid: 1000
    gid: 1000

runtime:
  backend: auto  # docker, podman, or auto
  privileged: false
  features:
    - gpu      # NVIDIA GPU access
    - audio    # PulseAudio/PipeWire
    - display  # X11/Wayland support

stages:
  base:
    from: python:3.11-slim
    packages:
      apt:
        - git
        - curl
        - build-essential
      pip:
        - numpy
        - pandas
        - scikit-learn
    env:
      MODEL_PATH: /models
      LOG_LEVEL: info
    cached_assets:
      - url: https://example.com/model.tar.gz
        dest: /models/model.tar.gz
    steps:
      - install_system_packages
      - install_pip_packages
      - copy_cached_assets
      - create_user
      - switch_user

  development:
    from: base
    packages:
      pip:
        - pytest
        - ipython
    env:
      DEBUG: "true"

  production:
    from: base
    steps:
      - COPY workspace ${WORKSPACE}

commands:
  train:
    command: "python workspace/train.py"
    description: "Train the model"
    env:
      CUDA_VISIBLE_DEVICES: "0"

  test:
    command: "pytest workspace/tests"
    description: "Run tests"

  serve:
    command: "python workspace/serve.py --port 8000"
    description: "Start API server"
```

### Configuration Reference

#### Project Section

```yaml
project:
  name: my-project           # Required: Container image name
  workspace: workspace       # Required: Directory containing your code
  auto_update: false         # Optional: Auto-regenerate on config change
  production_user:           # Optional: User for production builds
    name: appuser
    uid: 1000
    gid: 1000
```

#### Runtime Section

```yaml
runtime:
  backend: auto              # docker, podman, or auto (default)
  privileged: false          # Run containers in privileged mode
  features:                  # Optional list of features
    - gpu                    # Enable NVIDIA GPU access
    - audio                  # Enable audio (PulseAudio/PipeWire)
    - display                # Enable display (X11/Wayland)
```

#### Stages Section

Define multi-stage Docker builds:

```yaml
stages:
  base:
    from: python:3.11-slim   # Base image or parent stage name
    shell: /bin/bash         # Optional: shell to use (default: bash)
    packages:
      apt: [package1, package2]
      apk: [package1]        # For Alpine images
      pip: [package1, package2]
    env:
      VAR_NAME: value
    cached_assets:
      - url: https://example.com/file.tar.gz
        dest: /path/in/container
    steps:                   # Optional: control build order
      - install_system_packages
      - install_pip_packages
      - copy_cached_assets
      - create_user
      - switch_user
      - COPY src /app/src   # Raw Dockerfile commands

  development:
    from: base               # Inherit from base stage
    packages:
      pip: [dev-package1]

  production:
    from: base
    steps:
      - COPY workspace ${WORKSPACE}
```

**Available build steps:**
- `install_system_packages` - Install apt/apk packages
- `install_pip_packages` - Install Python packages
- `copy_cached_assets` - Copy downloaded cached assets
- `create_user` - Create the production user
- `switch_user` - Switch to the production user
- Raw Dockerfile commands (e.g., `COPY`, `RUN`, `ENV`)

#### Commands Section

Define custom commands that work in both development and production:

```yaml
commands:
  command-name:
    command: "python workspace/script.py"
    description: "Description of what this does"
    env:                     # Optional: environment variables
      VAR_NAME: value
```

Usage:
```bash
# Development
just command-name

# Production
./run.sh command-name
```

## Commands

### Project Management

```bash
cm init <template> [name]    # Create new project from template
  --here                     # Initialize in current directory
  --compact                  # Generate compact YAML (no comments)

cm update                    # Regenerate all files from YAML
cmupdate                     # Alias for cm update
```

### Templates

Available templates:
- `python` or `python:3.11` - Python base images
- `ubuntu` or `ubuntu:22.04` - Ubuntu base images
- `debian` - Debian base
- `alpine` - Alpine Linux
- `pytorch/pytorch` or `pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime` - PyTorch images
- `nvidia/cuda:12.4.0-runtime-ubuntu22.04` - NVIDIA CUDA images

### Using Just (Development)

After `cm init` or `cm update`:

```bash
just build                   # Build development image
just run python script.py    # Run command in container
just shell                   # Interactive shell
just clean                   # Remove containers
just clean-images            # Remove images

# Custom commands (if defined in config)
just train                   # Run training
just test                    # Run tests
```

### Using Standalone Scripts (Production)

```bash
./build.sh                   # Build production image
./run.sh python script.py    # Run command
./run.sh                     # Interactive shell

# Custom commands (if defined in config)
./run.sh train              # Run training
./run.sh test               # Run tests
```

## Development vs Production

### Development Workflow

Uses **Justfile** for rapid iteration with workspace mounting:

```bash
just build                  # Build development image
just run python script.py   # Run with live code mounting
just shell                  # Interactive shell
```

**Development mode:**
- Mounts workspace from host (live code editing)
- Runs as your user (correct file permissions)
- Includes development packages
- Uses development image tag

### Production Workflow

Uses **standalone scripts** that work without dependencies:

```bash
./build.sh                  # Build production image
./run.sh python script.py   # Run production container
```

**Production mode:**
- Workspace baked into image
- Minimal image size
- Runs as configured user (non-root)
- Only requires `docker` or `podman`
- Scripts can be committed and used anywhere

## Repository Structure

```
my-project/
├── cm.yaml                   # Configuration (edit this)
│   or container-magic.yaml
├── Dockerfile                # Generated (committed)
├── Justfile                  # Generated (committed, for dev)
├── build.sh                  # Generated (committed, for prod)
├── run.sh                    # Generated (committed, for prod)
├── workspace/                # Your code
│   ├── main.py
│   └── tests/
├── .gitignore
└── .cm-cache/                # Downloaded cached assets (not committed)
```

## Advanced Features

### Cached Assets

Download large files once and cache them:

```yaml
stages:
  base:
    cached_assets:
      - url: https://huggingface.co/model.tar.gz
        dest: /models/model.tar.gz
    steps:
      - copy_cached_assets  # Must include in build steps
```

Assets are downloaded to `.cm-cache/` and copied during build. The cache directory is in `.gitignore`.

### Custom Build Steps

Control the exact order of Dockerfile operations:

```yaml
stages:
  base:
    steps:
      - install_system_packages
      - RUN echo "Custom command here"
      - install_pip_packages
      - create_user
      - COPY config.json /app/
      - switch_user
```

### Multiple Stages

```yaml
stages:
  base:
    from: python:3.11-slim
    packages:
      apt: [build-essential]

  development:
    from: base
    packages:
      pip: [pytest, black, ruff]

  production:
    from: base  # Inherits from base, not development
    steps:
      - COPY workspace ${WORKSPACE}
```

### Auto-Update

Enable automatic regeneration when config changes:

```yaml
project:
  auto_update: true
```

Now `just build` will auto-regenerate if `cm.yaml` changed.

## Architecture

Container-magic is built with:
- **Python** - Core CLI tool
- **YAML** - Configuration format
- **Jinja2** - Template engine for generating files
- **Just** - Task runner for development workflow
- **Docker/Podman** - Container runtimes (auto-detected)

The tool acts as a "compiler" that transforms declarative YAML configuration into executable artifacts. Once generated, projects are self-contained and don't require container-magic for daily use.

## Design Philosophy

1. **YAML as source of truth** - All configuration in one place
2. **Generate, don't abstract** - Produce readable files you can inspect and modify
3. **Standalone after generation** - Development uses Just, production uses zero dependencies
4. **Auto-sync** - Regenerate when configuration changes, warn if out of sync
5. **Clear dev/prod separation** - Different tools for different workflows
6. **Validation** - Comprehensive linting and formatting checks

## Comparison with Docker-BBQ

Container-magic is the successor to [docker-bbq](https://github.com/markhedleyjones/docker-bbq) with these improvements:

- **YAML configuration** instead of scattered Makefile variables and `.docker-bbq` files
- **Python-based** instead of shell scripts (better error handling, testing, extensibility)
- **Just integration** instead of Make (more powerful, cross-platform)
- **Generated artifacts** are committed (reviewable in PRs, works without cm installed)
- **Custom commands** that work in both dev and prod
- **Validation** of configuration with helpful error messages
- **Multi-stage builds** with flexible step ordering
- **Cached assets** support for large model files

## Contributing

Container-magic is in early development. Contributions, ideas, and feedback welcome!

## License

MIT License
