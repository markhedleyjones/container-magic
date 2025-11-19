# container-magic

A tool for rapidly creating containerised development environments with a focus on simplicity and portability. Configure once in YAML, use anywhere with Docker or Podman.

This tool might be useful if you:
1. Want consistent, reproducible development environments across projects
2. Are tired of manually writing Dockerfiles and docker run commands
3. Work across multiple container-based repositories and want a unified workflow
4. Need smart handling of display (X11/Wayland), GPU, and workspace mounting

## Features

* **YAML-driven configuration** - Single source of truth for your entire container setup
* **Smart `run` command** - Seamlessly execute code in containers with automatic workspace mounting, GPU, and display support
* **Generated artifacts** - Produces Dockerfile, Justfile, and standalone scripts that work without container-magic installed
* **Template system** - Start new projects instantly with proven templates (Python, Ubuntu, Debian, ROS, etc.)
* **Docker and Podman support** - Automatically detects and works with either container runtime
* **Development/Production builds** - Separate workflows optimised for each use case
* **Standalone production scripts** - Generated `build.sh` and `run.sh` work with no dependencies

## Quick Start

### Installation

```bash
pip install container-magic
```

This installs two commands:
- `cm` - Main container-magic CLI
- `run` - Quick command execution (docker-bbq style)

### Create a New Project

```bash
# Initialize from template
cm init python my-analytics-project
cd my-analytics-project

# Edit configuration
vim container-magic.yaml

# Build and run
cm build
cm run python analyze.py

# Or use the quick 'run' command
run python analyze.py
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
container-magic.yaml  ──┐
  (source of truth)     │
                        ├─> cm init/update/generate
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

Example `container-magic.yaml`:

```yaml
project:
  name: my-project
  workspace: workspace

runtime:
  backend: auto  # docker, podman, or auto
  privileged: false

template:
  base: python:3-slim
  packages:
    apt: [git, curl, build-essential]
    pip: [numpy, pandas, matplotlib]
  build_steps:
    # Control where custom RUN commands appear in the Dockerfile
    before_packages:
      - echo "deb http://custom-repo.example.com/apt stable main" > /etc/apt/sources.list.d/custom.list
    after_packages:
      - mkdir -p /app/models
      - |
        curl -o /app/models/data.tar.gz https://example.com/models.tar.gz && \
        tar -xzf /app/models/data.tar.gz -C /app/models
    after_user:
      - mkdir -p /home/${USER_NAME}/.config
      - chown ${USER_UID}:${USER_GID} /home/${USER_NAME}/.config

development:
  mount_workspace: true
  shell: /bin/bash
  features:
    - display    # X11/Wayland support
    - gpu        # NVIDIA GPU access
    - audio      # PulseAudio/PipeWire

production:
  user: nonroot
  entrypoint: /workspace/main.py
```

When you run `cm build` or `cm update`, this generates a Dockerfile, Justfile, and standalone scripts tailored to your configuration.

## Commands

### Project Management

```bash
cm init <template> <name>    # Create new project from template
cm update                    # Regenerate all files from YAML
cm generate                  # Alias for cm update
cm build                     # Build container image (auto-updates if YAML changed)
```

### Running Code

```bash
cm run <command> [args]      # Run command in container
cm shell                     # Interactive shell in container

# Or use the quick 'run' command (works from anywhere)
run python script.py
run ~/repos/my-project/workspace/analyze.py
```

### Using Just Directly

After `cm init` or `cm update`, you can use `just` commands:

```bash
just build                   # Build development image
just run python script.py    # Run command in container
just shell                   # Interactive shell
```

## Templates

Available templates (MVP):

- **python** - Python 3 with pip support
- **ubuntu** - Ubuntu base with apt packages
- **debian** - Debian slim base

Future templates:
- **ros** - ROS Noetic
- **ros2** - ROS 2 Humble/Jazzy
- **alpine** - Minimal Alpine Linux

## Development vs Production

Container-magic supports two distinct workflows:

### Development Workflow

Uses **Just** for rapid iteration with workspace mounting:

```bash
# Build development image
just build
# or
cm build

# Run commands with live code mounting
just run python script.py
cm run python script.py

# Interactive shell
just shell
cm shell
```

**Development mode**:
- Mounts workspace from host (live code editing)
- Runs as your user (correct file permissions)
- Includes development tools
- Requires `just` installed

### Production Workflow

Uses **standalone scripts** that work without any dependencies:

```bash
# Build production image (no cm or just needed)
./build.sh

# Run production container (no cm or just needed)
./run.sh python script.py
./run.sh                    # Interactive shell
```

**Production mode**:
- Workspace baked into image
- Minimal image size
- Runs as non-root user
- Only requires `docker` or `podman`
- Scripts can be committed and used anywhere

The standalone scripts (`build.sh` and `run.sh`) are generated by container-magic but have zero dependencies once created. This means you can distribute your project and users can build and run it without installing container-magic or just.

## Repository Structure

```
my-project/
├── container-magic.yaml      # Configuration (edit this)
├── Dockerfile                # Generated from YAML (committed)
├── Justfile                  # Generated from YAML (committed, for dev)
├── build.sh                  # Generated from YAML (committed, for prod)
├── run.sh                    # Generated from YAML (committed, for prod)
├── workspace/                # Your code goes here
│   └── main.py
└── .gitignore
```

## Architecture

Container-magic is built with:
- **Python** - Core CLI tool
- **YAML** - Configuration format
- **Jinja2** - Template engine for generating Dockerfiles and Justfiles
- **Just** - Task runner for daily workflow
- **Docker/Podman** - Container runtimes (auto-detected)

The tool acts as a "compiler" that transforms declarative YAML configuration into executable artifacts (Dockerfile, Justfile, build.sh, run.sh). Once generated, projects are self-contained and don't require container-magic for daily use.

## Design Philosophy

1. **YAML as source of truth** - All configuration in one place
2. **Generate, don't abstract** - Produce readable files you can inspect and modify
3. **Standalone after generation** - Development uses just, production uses zero dependencies
4. **Auto-sync** - Regenerate when configuration changes, warn if out of sync
5. **Clear dev/prod separation** - Different tools for different workflows

## Comparison with Docker-BBQ

Container-magic is the successor to [docker-bbq](https://github.com/markhedleyjones/docker-bbq) with these improvements:

- **YAML configuration** instead of scattered Makefile variables and .docker-bbq files
- **Python-based** instead of shell scripts (better error handling, testing, extensibility)
- **Just integration** instead of Make (more powerful, cross-platform)
- **Generated artifacts** are committed (reviewable in PRs, works without cm installed)
- **Validation** of configuration with helpful error messages

## Contributing

Container-magic is in early development. Contributions, ideas, and feedback welcome!

## License

MIT License
