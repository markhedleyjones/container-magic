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

### User

```yaml
user:
  development:
    host: true              # Use your host UID/GID at build time
  production:
    name: appuser           # Required: username
    uid: 1000               # Optional (default: 1000)
    gid: 1000               # Optional (default: 1000)
    home: /home/appuser     # Optional (default: /home/${name})
```

The `development` target with `host: true` captures your actual UID/GID when building, so file permissions match your host user. The `production` target defines a fixed user baked into the image.

If no `user` section is defined, containers run as root.

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

  serve:
    command: python -m http.server 8000
    description: Start dev server
    ports:
      - "8000:8000"
```

**Command options:**
- `command` - The command to run (supports multi-line via YAML `|` syntax)
- `description` - Help text shown in Justfile
- `args` - Positional arguments (see below)
- `env` - Environment variables passed to the container
- `ports` - Ports to publish to the host (`host:container` format, generates `--publish` flags)
- `standalone` - Generate a dedicated `<command>.sh` script

### Command Arguments

Commands can define positional arguments with type validation and optional file/directory mounting:

```yaml
commands:
  process:
    command: "python process.py {input} {output}"
    description: "Process input file"
    args:
      input:
        type: file
        description: "Input file to process"
      output:
        type: file
        default: ""           # Makes this argument optional
        readonly: false       # Allow writing to this path
        mount_as: /tmp/out    # Mount at this container path
```

**Argument options:**
- `type` - One of: `file`, `directory`, `string`, `int`, `float`
- `description` - Help text for the argument
- `default` - Default value (makes the argument optional)
- `readonly` - For file/directory types: validate existence (default: `true`)
- `mount_as` - For file/directory types: mount at this container path

**Generated Just recipe:**
```
process input output="" *args:
```

Required arguments come first, followed by optional arguments with their defaults. The `{arg_name}` placeholders in the command are substituted with the actual values (or mount paths if `mount_as` is specified).

**Passing extra flags:**

All commands include `*args` which captures any additional arguments (including flags) and appends them to the command:

```bash
just process input.txt --verbose --dry-run
# Runs: python process.py input.txt --verbose --dry-run

just process input.txt output.txt --format=json
# Runs: python process.py input.txt output.txt --format=json
```

This allows passing through any flags your underlying command supports without needing to define them in the YAML.

**Example with file mounting:**
```yaml
commands:
  convert:
    command: "ffmpeg -i {input} {output}"
    args:
      input:
        type: file
        mount_as: /tmp/input.mp4
      output:
        type: file
        default: ""
        readonly: false
        mount_as: /tmp/output.mp4
```

When `mount_as` is specified, the host file is mounted into the container at that path, and the command uses the container path. This is useful for tools that expect specific paths or when you need to isolate container access.

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
user:
  production:
    name: appuser      # This user is baked into the image
    uid: 1000
    gid: 1000
```

If no `user.production` is defined, **the container runs as root** (`root` user with UID 0).

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

**Requires:** `user.production` defined in config (with at least `name` field)

**Field Defaults:**
- `uid`: 1000 (if not specified)
- `gid`: 1000 (if not specified)
- `home`: `/home/${name}` (if not specified)

**Example:**
```yaml
user:
  production:
    name: appuser

stages:
  base:
    from: python:3.11-slim
    steps:
      - create_user  # Creates user with uid=1000, gid=1000, home=/home/appuser
```

**Generated Dockerfile:** Creates user and group with specified IDs, skips if user is "root"

---

#### 4. `become_user`

Switches the current user context from root to the configured non-root user. Also sets the user context for subsequent `copy` steps.

**Requires:** `create_user` step in same or parent stage, user config defined

**Alias:** `switch_user` (deprecated, still works)

**Example:**
```yaml
stages:
  production:
    from: base
    steps:
      - create_user
      - become_user
      - copy app /app
```

**Generated Dockerfile:** Sets `USER user`

**Use case:** Run application as non-root for security

---

#### 5. `become_root`

Switches user context back to root (if needed after `become_user`).

**Requires:** `become_user` step executed previously

**Alias:** `switch_root` (deprecated, still works)

**Example:**
```yaml
stages:
  production:
    steps:
      - become_user
      - RUN echo "running as user"
      - become_root
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

#### 8. `copy`

User-context-aware file copy. Behaves like Docker's `COPY` but automatically adds `--chown=${USER_UID}:${USER_GID}` when `become_user` is active. This follows the container-magic convention: lowercase = smart abstraction, uppercase = raw Dockerfile passthrough.

**Example:**
```yaml
stages:
  base:
    from: python:3.11-slim
    steps:
      - create_user
      - become_user
      - copy app /app
      - copy config.yaml /etc/app/config.yaml
```

**Generated Dockerfile:**
```dockerfile
COPY --chown=${USER_UID}:${USER_GID} app /app
COPY --chown=${USER_UID}:${USER_GID} config.yaml /etc/app/config.yaml
```

If the `copy` step appears before `become_user` or after `become_root`, it generates a plain `COPY` without `--chown`. User context is inherited from parent stages — if a parent ends with `become_user`, child stages start with user context active.

**Use case:** Copy files into the image with correct ownership, without manually adding `--chown` flags.

---

#### 9. `copy_as_user`

Copies files with user ownership regardless of the current user context. Always adds `--chown=${USER_UID}:${USER_GID}`.

**Example:**
```yaml
steps:
  - create_user
  - copy_as_user config/app.conf /home/appuser/.config/
  - become_user
```

**Use case:** Set up user-owned files while still running as root, before switching context.

---

#### 10. `copy_as_root`

Copies files with root ownership regardless of the current user context. Never adds `--chown`.

**Example:**
```yaml
steps:
  - create_user
  - become_user
  - copy_as_root config/system.conf /etc/app/
  - copy app /home/appuser/app
```

**Use case:** Copy root-owned system files without needing to switch context back and forth. Equivalent to uppercase `COPY` but keeps your steps in the container-magic vocabulary.

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

user:
  production:
    name: appuser

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
      - become_user
      - copy app /app
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
- `COPY` / `ADD` - Copy files (uppercase passes through as-is; use lowercase `copy` for automatic `--chown` when running as non-root)
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
    "create_user",  # Only if user.production configured
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
2. **User creation before switching** - `create_user` must come before `become_user`
3. **Packages before custom commands** - Install system/pip packages before using them
4. **Assets before commands** - Copy cached assets before commands that use them
5. **User switching for security** - Switch to non-root after setup, use `copy_as_root` or `become_root` if needed for privileged ops

**Common approach:**
```yaml
steps:
  - install_system_packages
  - install_pip_packages
  - copy_cached_assets
  - create_user
  - become_user
  - copy app /app
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
      - become_user
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
    steps:
      - ENV NODE_ENV=production
      - ENV PATH=/app/node_modules/.bin:$PATH
      - RUN npm install --global yarn
```

---

### Validation Rules

Container-magic validates your step configuration:

| Rule | Error | Solution |
|------|-------|----------|
| `become_user` without `create_user` | Warning | Add `create_user` step before `become_user` |
| `create_user` without user config | Error | Define `user.production` in config |
| `become_user` without user config | Error | Define `user.production` in config |
| `cached_assets` without `copy_cached_assets` | Warning | Add `copy_cached_assets` step to use assets |

---

### Troubleshooting Steps

**Q: "Error: uses 'create_user' or 'become_user' but production.user is not defined"**

A: Add a `user.production` section to your config:
```yaml
user:
  production:
    name: appuser
```

**Q: Custom step not producing expected output**

A: Steps that don't match a built-in keyword or Dockerfile instruction are automatically wrapped with `RUN`. Both of these are equivalent:
```yaml
steps:
  - RUN apt-get install -y something     # explicit RUN
  - apt-get install -y something         # RUN is prepended automatically
```
For other Dockerfile instructions (`ENV`, `COPY`, `WORKDIR`, etc.), use the uppercase keyword explicitly.

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

A: Use lowercase `copy` instead of uppercase `COPY` — it automatically sets ownership via `--chown` when `become_user` is active:
```yaml
steps:
  - create_user
  - become_user
  - copy app /app
```

## Contributing

Container-magic is in early development. Contributions and feedback welcome!
