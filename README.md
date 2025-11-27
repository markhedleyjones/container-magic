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
./build.sh              # Builds the default target (production) → tagged as 'latest'
./build.sh production   # Builds production stage → tagged as 'latest'
./build.sh testing      # Builds testing stage → tagged as 'testing'
./build.sh development  # Builds development stage → tagged as 'development'
./build.sh --help       # Shows all available targets
```

**Image Tagging:**
- Production stage is tagged as `<project-name>:latest`
- All other stages are tagged as `<project-name>:<stage-name>`

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

## User Handling

Container-magic handles users differently for development and production:

### Development (`build` and `run` commands)

When you run `build` or `run`, the container is built and run as **your current system user**:

```bash
# The build command captures:
USER_UID=$(id --user)            # Your UID
USER_GID=$(id --group)           # Your GID
USER_NAME=$(id --user --name)    # Your username
USER_HOME=$(echo ~)              # Your home directory
```

This means:
- You run commands as yourself (same UID/GID as your host)
- Your home directory is mapped into the container
- File permissions are correct (no permission issues)
- You can edit code on the host and run it in the container seamlessly

### Production (`./build.sh` and `./run.sh`)

The standalone production scripts use the user configuration from your `cm.yaml`:

```yaml
project:
  production_user:
    name: user         # This user is baked into the image
    uid: 1000
    gid: 1000
```

If no `production_user` is defined, **the container runs as root** (`root` user with UID 0).

**Note:** When no user is configured:
- The `run.sh` script still works correctly
- Commands execute with root privileges
- This is the default Docker/Podman behavior (no `USER` directive means root)

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

## Python pip on Debian/Ubuntu

Modern versions of Debian (12+) and Ubuntu (24.04+) enforce [PEP 668](https://peps.python.org/pep-0668/), which prevents pip from installing packages system-wide. If you try to use pip on these distributions, you'll encounter an error.

**Solution:** Use one of these approaches:

1. **Use a Python official image**:
   ```yaml
   stages:
     base:
       from: python:3.11-slim
       packages:
         pip: [requests, numpy]
   ```

2. **Install `python3-full`**:
   ```yaml
   stages:
     base:
       from: ubuntu:24.04
       packages:
         apt: [python3-full]
         pip: [requests]
   ```

3. **Use a custom step** with the `--break-system-packages` flag (if you understand the security implications):
   ```yaml
   stages:
     base:
       from: ubuntu:24.04
       packages:
         apt: [python3, python3-pip]
       steps:
         - install_system_packages
         - RUN pip install --break-system-packages requests
   ```

## Build Steps Reference

The `steps` field (or legacy `build_steps`) in each stage defines how the image is constructed. Container-magic provides built-in steps for common tasks, and supports custom Dockerfile commands for advanced use cases.

### Built-in Steps

#### 1. `install_system_packages`

Installs system packages using the distribution's package manager (APT, APK, or DNF).

**Requires:** `packages.apt`, `packages.apk`, or `packages.dnf` defined

**Example:**
```yaml
stages:
  base:
    from: ubuntu:24.04
    packages:
      apt: [curl, git, build-essential]
    steps:
      - install_system_packages
```

**Generated Dockerfile:** Runs `apt-get update && apt-get install` (with cleanup)

---

#### 2. `install_pip_packages`

Installs Python packages using pip.

**Requires:** `packages.pip` defined

**Example:**
```yaml
stages:
  base:
    from: python:3.11-slim
    packages:
      pip: [requests, pytest, numpy]
    steps:
      - install_pip_packages
```

**Generated Dockerfile:** Runs `pip install --no-cache-dir`

---

#### 3. `create_user`

Creates a non-root user account for running the application.

**Condition:** Only created if `production_user` is defined in config (with required `name` field)

**Field Defaults:**
- `uid`: 1000 (if not specified)
- `gid`: 1000 (if not specified)
- `home`: `/home/${name}` (if not specified)

**Example:**
```yaml
project:
  production_user:
    name: user
    uid: 1000
    gid: 1000
    home: /home/user

stages:
  production:
    from: base
    steps:
      - create_user
```

Minimal example (using defaults):
```yaml
project:
  production_user:
    name: user  # Only required field

stages:
  production:
    steps:
      - create_user  # Creates user with uid=1000, gid=1000, home=/home/user
```

**Generated Dockerfile:** Creates user and group with specified IDs

**Notes:**
- User UID/GID are passed as build arguments to ensure consistency across builds
- Automatically skips creation if user is "root"
- If any field is defined (name, uid, gid, or home), the user will be created

---

#### 4. `switch_user`

Switches the current user context from root to the configured non-root user.

**Requires:** `create_user` step in same or parent stage, `production_user` defined

**Example:**
```yaml
stages:
  production:
    from: base
    steps:
      - create_user
      - switch_user
      - COPY app /app
      - RUN chown -R ${USER_NAME}:${USER_NAME} /app
```

**Generated Dockerfile:** Sets `USER user`

**Use case:** Run application as non-root for security

---

#### 5. `switch_root`

Switches user context back to root (if needed after `switch_user`).

**Requires:** `switch_user` step executed previously

**Example:**
```yaml
stages:
  production:
    steps:
      - switch_user
      - RUN echo "running as user"
      - switch_root
      - RUN echo "back to root"
```

**Generated Dockerfile:** Sets `USER root`

**Use case:** Temporarily switch to root for privileged operations

---

#### 6. `copy_cached_assets`

Copies pre-downloaded assets into the image (avoids re-downloading during builds).

**Requires:** `cached_assets` defined in stage

**Generated Dockerfile:** Copies files from build cache into image with `--chown` applied automatically if a user is configured

**Notes:**
- Must be explicitly added to `steps` to copy assets into image (assets are downloaded but not used if step is missing)
- If a user is configured, ownership is automatically set via `--chown=${USER_UID}:${USER_GID}`
- See "Downloading and Caching Assets" section below for detailed usage and configuration

---

#### 7. `copy_workspace`

Copies the entire workspace directory into the image (typically for production builds).

**Example:**
```yaml
stages:
  production:
    from: base
    steps:
      - copy_workspace
```

**Generated Dockerfile:**
- Without user: `COPY workspace ${WORKSPACE}`
- With user: `COPY --chown=${USER_UID}:${USER_GID} workspace ${WORKSPACE}`

**Use case:** Include application code in production image

**Notes:**
- Automatic default step for production stage if not specified
- Uses `WORKSPACE` environment variable (default: `/root/workspace`)
- If `create_user` step is used, automatically applies `--chown` with the user's UID/GID to set proper file ownership

---

### Downloading and Caching Assets

Container-magic supports downloading external resources (files, models, datasets) and caching them locally to avoid re-downloading on subsequent builds. Use the `copy_cached_assets` step (see step 6 above) to include cached assets in your image.

**Use cases:**
- Machine learning models from HuggingFace or other sources
- Large datasets
- Pre-compiled binaries or libraries
- Configuration files from remote sources

**Configuration:**

Define assets under `cached_assets` in any stage:

```yaml
stages:
  base:
    from: python:3.11-slim
    cached_assets:
      - url: https://example.com/model.tar.gz
        dest: /models/model.tar.gz
      - url: https://huggingface.co/bert-base-uncased/resolve/main/model.safetensors
        dest: /models/bert.safetensors
    steps:
      - copy_cached_assets
```

**Configuration options:**
- `url` (required) - HTTP(S) URL to download from
- `dest` (required) - Destination path inside container

**How it works:**

1. Run `cm update` or `cm build` - assets are downloaded (if not cached) with 60-second timeout
2. Files cached in `.cm-cache/assets/<url-hash>/` with `meta.json` metadata
3. Add `copy_cached_assets` to your stage's `steps` to copy into image
4. Subsequent builds reuse cached files, skipping downloads

**Cache management:**
```bash
cm cache list    # List cached assets with size and URL
cm cache path    # Show cache directory location
cm cache clear   # Clear all cached assets
```

**Example: ML model in production image**

```yaml
project:
  name: ml-service
  production_user:
    name: user
    uid: 1000
    gid: 1000
    home: /home/user

stages:
  base:
    from: pytorch/pytorch:latest
    packages:
      pip: [transformers, flask]
    cached_assets:
      - url: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/main/pytorch_model.bin
        dest: /models/model.bin
    steps:
      - install_pip_packages
      - copy_cached_assets

  production:
    from: base
    steps:
      - create_user
      - switch_user
      - COPY app /app
      - RUN chown -R ${USER_NAME}:${USER_NAME} /app
```

**Downloading during different build stages:**

All stages with `cached_assets` download when running `cm build`:

```yaml
stages:
  base:
    cached_assets:
      - url: https://example.com/base-asset.tar.gz
        dest: /opt/base-asset.tar.gz
    steps:
      - copy_cached_assets

  development:
    from: base
    cached_assets:
      - url: https://example.com/dev-asset.zip
        dest: /opt/dev-asset.zip
    steps:
      - copy_cached_assets

  production:
    from: base
    cached_assets:
      - url: https://example.com/prod-asset.tar.gz
        dest: /opt/prod-asset.tar.gz
    steps:
      - copy_cached_assets
```

All three assets are downloaded and available for their respective stages.

---

### Custom Dockerfile Commands

You can include raw Dockerfile commands as steps. Any string that doesn't match a built-in keyword is treated as a custom command.

**Example:**
```yaml
stages:
  base:
    from: ubuntu:24.04
    packages:
      apt: [python3, python3-pip]
    steps:
      - install_system_packages
      - install_pip_packages
      - RUN pip install --break-system-packages requests
      - ENV APP_MODE=production
      - WORKDIR /app
      - LABEL maintainer="you@example.com"
```

**Supported Dockerfile instructions:**
- `RUN` - Execute commands
- `ENV` - Set environment variables
- `WORKDIR` - Change working directory
- `COPY` / `ADD` - Copy files
- `EXPOSE` - Expose ports
- `LABEL` - Add metadata
- Any other valid Dockerfile instruction

**Variable substitution in Dockerfile steps:** You can reference container-magic variables:
- `${WORKSPACE}` - Workspace directory path
- `${WORKDIR}` - Working directory
- `${USER_NAME}` - Non-root user name (if configured)
- `${USER_UID}` / `${USER_GID}` - User IDs

---

### Using `$WORKSPACE` in container scripts

The `$WORKSPACE` environment variable is **automatically set inside every container** and points to your workspace directory. This is set at build time in the Dockerfile, so scripts can rely on it without any extra setup.

**Inside the container**, use `$WORKSPACE` to reference files without manual path construction:

```bash
# Good - uses $WORKSPACE variable set at build time
bash $WORKSPACE/scripts/commands.sh preprocess

# Less ideal - manual path construction
bash /home/user/workspace/scripts/commands.sh preprocess
```

**In custom commands, reference workspace files cleanly:**

```yaml
commands:
  process:
    command: python $WORKSPACE/scripts/process.py
    description: Process workspace data
```

**In Dockerfile steps, use `${WORKSPACE}` to reference workspace files:**

```yaml
stages:
  base:
    from: python:3.11
    steps:
      - copy_workspace
      - RUN python ${WORKSPACE}/setup.py build
      - RUN ${WORKSPACE}/scripts/init.sh
```

This eliminates the need to manually construct paths like `$HOME/workspace/ros2_ws/scripts/...` - just use `$WORKSPACE` which is always available and pre-configured.

---

### Default Step Behaviour

If you don't specify `steps`, container-magic applies defaults based on the stage type:

**For stages FROM Docker images** (e.g., `from: python:3.11-slim`):
```python
steps = [
    "install_system_packages",
    "install_pip_packages",
    "create_user",  # Only if production_user configured
]
```

**For stages FROM other stages** (e.g., `from: base`):
```python
steps = []  # Inherits packages from parent
```

**For production stage:**
```python
steps = ["copy_workspace"]  # If not overridden
```

---

### Step Ordering Rules

1. **Steps execute in order** - Left to right, top to bottom
2. **User creation before switching** - `create_user` must come before `switch_user`
3. **Packages before custom commands** - Install system/pip packages before using them
4. **Assets before commands** - Copy cached assets before commands that use them
5. **User switching for security** - Switch to non-root after setup, switch back if needed for privileged ops

**Common approach:**
```yaml
steps:
  - install_system_packages
  - install_pip_packages
  - copy_cached_assets
  - create_user
  - switch_user
  - COPY app /app
  - RUN chown -R ${USER_NAME}:${USER_NAME} /app
```

---

### Common Patterns

#### Multi-stage with shared base

```yaml
stages:
  base:
    from: python:3.11-slim
    packages:
      apt: [git, build-essential]
      pip: [setuptools]
    steps:
      - install_system_packages
      - install_pip_packages

  development:
    from: base
    packages:
      pip: [pytest, black, mypy]
    # Steps automatically inherited from base

  production:
    from: base
    packages:
      pip: [gunicorn]
    steps:
      - create_user
      - switch_user
      - copy_workspace
```

#### Using cached assets for models

```yaml
stages:
  base:
    from: pytorch/pytorch:latest
    packages:
      pip: [transformers]
    cached_assets:
      - url: https://huggingface.co/bert-base-uncased/resolve/main/model.safetensors
        dest: /models/bert.safetensors
    steps:
      - install_pip_packages
      - copy_cached_assets
      - RUN python -c "from transformers import AutoModel; AutoModel.from_pretrained('/models')"
```

#### Custom build steps with environment

```yaml
stages:
  base:
    from: node:18-alpine
    packages:
      npm: [npm-check-updates]
    steps:
      - install_system_packages
      - ENV NODE_ENV=production
      - ENV PATH=/app/node_modules/.bin:$PATH
      - RUN npm install --global yarn
```

---

### Validation Rules

Container-magic validates your step configuration:

| Rule | Error | Solution |
|------|-------|----------|
| `switch_user` without `create_user` | Warning | Add `create_user` step before `switch_user` |
| `create_user` without `production_user` | Error | Define `project.production_user` in config |
| `switch_user` without `production_user` | Error | Define `project.production_user` in config |
| `cached_assets` without `copy_cached_assets` | Warning | Add `copy_cached_assets` step to use assets |

---

### Troubleshooting Steps

**Q: "Error: create_user step requires production_user to be configured"**

A: Add `production_user` to your config:
```yaml
project:
  name: my-app
  production_user:
    name: user
    uid: 1000
    gid: 1000
    home: /home/user
```

**Q: Custom RUN step not executing**

A: Verify step syntax - must start with Dockerfile command:
```yaml
# ✓ Correct
steps:
  - RUN apt-get install something
  - ENV VAR=value

# ✗ Incorrect (missing command keyword)
steps:
  - apt-get install something
```

**Q: Build takes too long when downloading assets**

A: Use `cached_assets` to download once and reuse:
```yaml
cached_assets:
  - url: https://large-file.example.com/model.tar.gz
    dest: /models/model.tar.gz
steps:
  - copy_cached_assets
```

**Q: Permission denied when running as non-root**

A: Ensure files are owned by the application user:
```yaml
steps:
  - create_user
  - switch_user
  - COPY app /app
  - RUN chown -R ${USER_NAME}:${USER_NAME} /app
```

## Contributing

Container-magic is in early development. Contributions and feedback welcome!
