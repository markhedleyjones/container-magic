---
hide:
  - toc
---

<div style="text-align: center;">
  <img src="https://raw.githubusercontent.com/markhedleyjones/container-magic-artwork/main/sparkles/original-vector.svg" alt="Container Magic - Sparkles the Otter" width="300"/>
  <h1>container-magic</h1>
  <p><strong>Rapidly create containerised development environments</strong></p>
  <p>Configure once in YAML, use anywhere with Docker or Podman</p>
</div>

## What It Does

Container-magic takes a single YAML configuration file and generates:

1. A **Dockerfile** with multi-stage builds
2. Standalone **build.sh** and **run.sh** scripts for production

The Dockerfile and standalone scripts are committed to your repository, so anyone can use your project with just `docker` or `podman` - no need to install container-magic.

For development, `cm build` and `cm run` read the YAML config directly and handle workspace mounting, user mapping, and feature flags automatically.

## Quick Start

```bash
# Install
pip install container-magic

# Create a new project
cm init python:3.11 my-project
cd my-project

# Build the container
cm build

# Run commands inside the container
cm run python --version
cm run bash -c "echo Hello from container"
cm run  # starts an interactive shell
```

See [Getting Started](getting-started.md) for a full walkthrough.

## Key Features

* **YAML configuration** - Single source of truth for your container setup
* **Transparent execution** - Run commands in container from anywhere in your repo
* **Custom commands** - Define commands once, use in both dev and prod
* **Smart features** - GPU, display (X11/Wayland), audio, and AWS credential support
* **Multi-stage builds** - Separate base, development, and production stages
* **Live workspace mounting** - Edit code on host, run in container (development)
* **Standalone scripts** - Production needs only docker/podman (no dependencies)
