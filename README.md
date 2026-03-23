<div align="center">
  <img src="https://raw.githubusercontent.com/markhedleyjones/container-magic-artwork/main/sparkles/original-vector.svg" alt="Container Magic - Sparkles the Otter" width="300"/>

  # container-magic

  **Turn a YAML file into a Dockerfile, build script, and run script that work with plain Docker or Podman - no tools to install, no dependencies to manage. One config gives you a live-mounted development environment and a production-ready image.**

  [![PyPI version](https://img.shields.io/pypi/v/container-magic.svg)](https://pypi.org/project/container-magic/)
  [![Python versions](https://img.shields.io/pypi/pyversions/container-magic.svg)](https://pypi.org/project/container-magic/)
  [![CI Status](https://github.com/markhedleyjones/container-magic/actions/workflows/ci.yml/badge.svg)](https://github.com/markhedleyjones/container-magic/actions/workflows/ci.yml)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
</div>

## How It Works

You write a `cm.yaml`. Container-magic generates a Dockerfile, `build.sh`, and `run.sh` from it. You commit those generated files to your repository.

Your colleagues run `./build.sh` and `./run.sh` with plain Docker or Podman. They never need to install container-magic.

When you change the config, you regenerate and commit. The generated files are always the source of truth for anyone without container-magic installed.

For your own development, `cm build` and `cm run` read the config directly and handle workspace mounting, user identity mapping, and runtime features automatically.

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

  development:
    from: base

  production:
    from: base
```

Your colleagues build and run the production image without container-magic:

```bash
./build.sh
./run.sh python workspace/train.py
```

## Key Features

* **Zero-dependency output** - generated Dockerfile, build.sh, and run.sh work with plain Docker or Podman
* **Development and production from one config** - live-mounted workspace in dev, baked-in code in prod
* **Automatic user handling** - host user identity in dev, dedicated user in prod, no manual setup
* **GPU, display, and audio** - NVIDIA GPU passthrough, X11/Wayland forwarding, PulseAudio/PipeWire
* **Custom commands** - define once, use in both dev and prod with port publishing and environment variables
* **Multi-stage builds** - share steps between stages, automatic virtual environments for pip
* **Transparent execution** - run commands from anywhere in your repo with automatic path translation
* **AWS credential forwarding** - mount host AWS config into the container
* **Cached assets** - download models and datasets once, reuse across builds
* **Docker and Podman** - works with either runtime, auto-detected

## Documentation

Full documentation is available at **[markhedleyjones.com/container-magic](https://markhedleyjones.com/container-magic/)**.

| Page | Contents |
|------|----------|
| [Getting Started](https://markhedleyjones.com/container-magic/getting-started/) | Installation, first project, workflow |
| [Configuration](https://markhedleyjones.com/container-magic/configuration/) | Full YAML reference - names, runtime, stages, commands |
| [Build Steps](https://markhedleyjones.com/container-magic/build-steps/) | Package managers, custom commands, layer caching |
| [Cached Assets](https://markhedleyjones.com/container-magic/cached-assets/) | Asset downloading, caching, and cache management |
| [User Handling](https://markhedleyjones.com/container-magic/user-handling/) | Dev vs prod users, copy ownership, permissions |
| [Troubleshooting](https://markhedleyjones.com/container-magic/troubleshooting/) | Common issues and solutions |

## Contributing

Contributions and feedback welcome! Open an issue or pull request on GitHub.
