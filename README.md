<div align="center">
  <img src="https://raw.githubusercontent.com/markhedleyjones/container-magic-artwork/main/sparkles/original-vector.svg" alt="Container Magic - Sparkles the Otter" width="300"/>

  # container-magic

  **Rapidly create containerised development environments**

  Configure once in YAML, use anywhere with Docker or Podman

  [![PyPI version](https://img.shields.io/pypi/v/container-magic.svg)](https://pypi.org/project/container-magic/)
  [![Python versions](https://img.shields.io/pypi/pyversions/container-magic.svg)](https://pypi.org/project/container-magic/)
  [![CI Status](https://github.com/markhedleyjones/container-magic/actions/workflows/ci.yml/badge.svg)](https://github.com/markhedleyjones/container-magic/actions/workflows/ci.yml)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  [![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
</div>

## What It Does

Container-magic takes a single YAML configuration file and generates:
1. A **Dockerfile** with multi-stage builds
2. Standalone **build.sh** and **run.sh** scripts for production

For development, `cm build` and `cm run` read the config directly and handle workspace mounting, user mapping, and feature flags automatically.

The generated files are committed to your repository, so anyone can use your project with just `docker` or `podman` - no need to install container-magic.

## Quick Start

```bash
pip install container-magic
cm init python:3.11 my-project
cd my-project
cm build
cm run python --version
```

A minimal `cm.yaml`:

```yaml
names:
  image: my-project
  workspace: workspace
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
    steps:
      - copy: workspace
```

## Key Features

* **YAML configuration** - single source of truth for your container setup
* **Transparent execution** - run commands from anywhere in your repo with automatic path translation
* **Custom commands** - define commands once, use in both dev and prod
* **Smart features** - GPU, display (X11/Wayland), and audio support
* **Multi-stage builds** - separate base, development, and production stages
* **Cached assets** - download models/datasets once, reuse across builds
* **Standalone scripts** - production needs only docker/podman

## Documentation

Full documentation is available at **[markhedleyjones.com/container-magic](https://markhedleyjones.com/container-magic/)**.

| Page | Contents |
|------|----------|
| [Getting Started](https://markhedleyjones.com/container-magic/getting-started/) | Installation, first project, workflow |
| [Configuration](https://markhedleyjones.com/container-magic/configuration/) | Full YAML reference - names, runtime, stages, commands |
| [Build Steps](https://markhedleyjones.com/container-magic/build-steps/) | Built-in steps, package managers, custom commands, layer caching |
| [Cached Assets](https://markhedleyjones.com/container-magic/cached-assets/) | Asset downloading, caching, and cache management |
| [User Handling](https://markhedleyjones.com/container-magic/user-handling/) | Dev vs prod users, copy ownership, permissions |
| [Troubleshooting](https://markhedleyjones.com/container-magic/troubleshooting/) | Common issues and solutions |

## Contributing

Container-magic is in early development. Contributions and feedback welcome!
