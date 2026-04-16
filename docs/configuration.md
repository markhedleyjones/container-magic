# Configuration

Container-magic is configured through a single YAML file (`cm.yaml`).

## Names

```yaml
names:
  image: my-project        # Required: image name
  workspace: workspace     # Workspace directory name (default: workspace)
  user: nonroot            # Required: container username
```

All three fields are shown above but only `image` and `user` are required (`workspace` defaults to `workspace`).

**`user`** controls the container's user identity:

- `user: root` - the container runs as root. No user management is needed or allowed; `create: user` and `become: user` are errors when `user` is `root`.
- `user: <name>` (any other value, e.g. `nonroot`, `appuser`) - a custom user is automatically created and the container switches to this user in leaf stages. See [User Handling](user-handling.md) for details.

Run `cm update` after editing `cm.yaml` to regenerate the Dockerfile and scripts. `cm build` also regenerates automatically before building.

## Backend

```yaml
backend: docker      # docker, podman, or auto (default: auto, omit for auto)
```

When set to `auto` (the default), container-magic will use whichever of `docker` or `podman` is available, preferring `docker`.

## Workspace Symlinks

When your workspace contains symlinks pointing outside the workspace directory, container-magic detects them and handles them automatically. No configuration is needed - `cm update` scans the workspace and generates the appropriate entries.

After adding or removing symlinks, run `cm update` to pick up the changes.

!!! info "How symlinks are handled"

    === "Development"

        Symlink targets are bind-mounted into the container at the matching
        workspace path. No rebuild needed - run `cm update` then `cm run`.

    === "Production"

        Symlink targets are resolved and copied into a staging directory,
        then baked into the image with additional `COPY` instructions.
        `cm build` runs `cm update` automatically before building.

Relative symlinks pointing within the workspace work naturally and aren't touched. Absolute symlinks pointing inside the workspace trigger a warning suggesting they be made relative for container compatibility. Dangling symlinks (where the target doesn't exist) are silently skipped.

## Environment File

`.env` files are automatically passed to the container via `--env-file`. Container-magic walks up from the project directory looking for `.env` files, loading them from most distant to closest so that closer values take precedence.

```
# .env (repository root)
API_KEY=sk-shared-key

# pdf/.env (project root)
WORKER_COUNT=4
```

Running `cm run` from `pdf/` loads both files. `pdf/.env` values override the parent `.env` if the same variable appears in both.

This works in both development (`cm run`) and production (`run.sh`). If no `.env` file is found in any parent directory, nothing happens.

## Runtime

```yaml
runtime:
  privileged: false  # privileged mode
  network_mode: host # host, bridge, or none (optional)
  ipc: shareable     # IPC namespace mode (optional)
  shell: /bin/bash   # interactive shell (auto-detected if not set)
  features:
    - gpu              # NVIDIA GPU
    - display          # X11/Wayland
    - audio            # PulseAudio/PipeWire
    - aws_credentials  # AWS credential forwarding
  volumes:
    - outputs                           # shorthand: ./outputs:/data/outputs
    - /host/path:/container/path        # bind mount
    - /host/path:/container/path:ro     # read-only bind mount
    - ~/.config/tool:~/.config/tool     # tilde expands to home directories
  devices:
    - /dev/video0:/dev/video0           # device passthrough
```

### Volumes

Volume paths support variable expansion. Each side of the colon is expanded independently - the left side (your machine) and the right side (inside the container) resolve to different values.

| Variable | Your machine | Inside the container |
|----------|-------------|---------------------|
| `~` | Your home directory | Container user's home directory |
| `$HOME` | Your home directory | Container user's home directory |
| `$WORKSPACE` | Project workspace directory | Container workspace directory |

Variables are expanded at the start of a path only. Options after the second colon (e.g. `ro`, `z`) are not affected.

```yaml
runtime:
  volumes:
    # Tilde expands differently on each side
    - ~/.config/tool:~/.config/tool

    # $HOME works the same way as tilde
    - $HOME/data:/mnt/data:ro

    # Workspace-relative paths
    - $WORKSPACE/output:$WORKSPACE/output
```

In the generated `run.sh`, `~` and `$HOME` on your side are rendered as `$HOME` for shell expansion at runtime. The container side is expanded to a literal path at generation time. Volumes using `$WORKSPACE` are not included in `run.sh` because the workspace is baked into the production image - a warning is printed during `cm update` if this applies.

#### Shorthand

A volume with no colon is shorthand. The container-side path is picked
automatically as `/data/<basename>`, where `<basename>` is the last path
segment of the host side. A colon is only needed when you want a different
container-side name.

```yaml
runtime:
  volumes:
    - outputs                      # ./outputs           -> /data/outputs
    - cache                        # ./cache             -> /data/cache
    - ../shared                    # ../shared           -> /data/shared
    - /srv/pipeline/outputs        # /srv/pipeline/...   -> /data/outputs
    - ~/datasets                   # ~/datasets          -> /data/datasets
```

Host-side path handling depends on whether the path is relative:

- **Relative paths** (bare names, `./x`, `../x`) are anchored to the project
  directory in development and to the directory containing `run.sh` in
  production. The host folder is created if missing.
- **Absolute paths**, `~/x`, and `$HOME/x` are self-sufficient and are
  passed through as-is. The host folder must already exist; container-magic
  will not create folders outside the project root.

The basename must match `[a-zA-Z0-9_-]+`. Paths that don't yield a valid
basename (`..`, `/`, empty strings, names with dots or spaces) are rejected
at config-parse time. Two volumes that resolve to the same container path
are also rejected as a collision - no silent clobbering.

Shorthand exists so bulk data (model outputs, caches, datasets) stays out of
the workspace and out of the built image. Operators deploying elsewhere can
read the container-side path directly from cm.yaml - it's always
`/data/<basename>`.

#### Multi-container setups

When several container-magic projects share the same data folder, put the
folder in a parent directory and reference it with `../`:

```
pipeline/
  shared/               <- written by scraper, read by trainer
  scraper/
    cm.yaml             <- volumes: - ../shared
    run.sh
  trainer/
    cm.yaml             <- volumes: - ../shared:/data/shared:ro
    run.sh              #  (full form used here for :ro)
```

Both projects see the shared folder at `/data/shared` inside their
respective containers. The scraper can write; the trainer reads only. Use
the full `host:container[:options]` form whenever you need `:ro` or other
mount options.

### Per-Stage Runtime

Stages can override or extend the global runtime configuration by adding a `runtime` block within the stage definition:

```yaml
runtime:
  features:
    - gpu

stages:
  development:
    from: base
    runtime:
      network_mode: host
      volumes:
        - ~/.local/bin/claude:/usr/local/bin/claude:ro
        - ~/.claude:~/.claude

  production:
    from: base
```

**Merge rules:**

- **Scalar fields** (network_mode, privileged, ipc, shell): stage value overrides the global value
- **List fields** (volumes, devices, features): stage values are appended to the global values

In the example above, `cm run` (development) gets `network_mode: host`, the Claude CLI mounts, and the global `gpu` feature. `run.sh` (production) gets only the global `gpu` feature with no extra volumes.

### Shell

The `shell` field sets the interactive shell used by `cm run` and `run.sh` when no command is given. If not set, it is auto-detected from the base image (Alpine uses `/bin/sh`, everything else uses `/bin/bash`). This does not affect `RUN` commands in the Dockerfile, which always use the container's standard shell.

### IPC Namespace

The `ipc` field sets the IPC namespace mode for containers (`--ipc` flag). Common values:

- `shareable` - allow other containers to share this container's IPC namespace
- `container:<name>` - join another container's IPC namespace
- `host` - use the host's IPC namespace
- `private` - container's own private IPC namespace (default)

Per-command overrides are supported via the `ipc` field on individual commands.

### Container Names

Development containers are named `<image-name>-development` and production containers are named `<image-name>`. If a container with the same name is already running, `cm run` will exec into the existing container instead of starting a new one. Running `cm run` with no arguments opens an interactive shell.

### Working Directory

In development, `cm run` sets the container's working directory to match your position relative to the project root. If you `cd workspace/src` on the host, the container starts in the corresponding `src` directory inside the workspace. This makes `cm run pytest` work naturally from a subdirectory.

In production, `run.sh` always starts in the workspace root regardless of where you invoke it from.

### Detached Mode

Containers can be started in the background:

- **Development:** `cm run --detach <command>` or `cm run -d <command>`
- **Production:** `./run.sh --detach <command>` or `./run.sh -d <command>`

To stop a detached container:

- **Development:** `cm stop`
- **Production:** `./run.sh --stop`

### Runtime Flag Passthrough

You can pass arbitrary flags directly to docker/podman using the `--` separator. Everything before `--` is passed to the container runtime; everything after `--` is the command to run.

```bash
# Pass environment variables
cm run -e DEBUG=1 -- my-command
./run.sh -e DEBUG=1 -- my-command

# Bind-mount a host directory
cm run -v /data:/data -- python process.py /data/input.csv

# Multiple flags
cm run -e DEBUG=1 -v /tmp:/data --net=host -- my-command --verbose

# Detach with passthrough
cm run -d -e WORKERS=4 -- python server.py
```

Without `--`, all arguments are treated as the command (backwards compatible). The `--` separator is only needed when you want to pass flags to docker/podman itself.

## Stages

Each container-magic project builds **one application** with two modes: development (workspace mounted from the host for live editing) and production (workspace copied into the image). Stages let you share build steps between these two modes via a common base.

```yaml
stages:
  base:
    from: python:3.11-slim    # Any Docker Hub image
    steps:
      - apt-get:
          install:
            - git
            - curl
      - pip:
          install:
            - numpy
            - pandas

  development:
    from: base                # Inherit from base
    steps:
      - pip:
          install:
            - pytest

  production:
    from: base
```

### Multiple applications

If you need genuinely different images - for example a data pipeline and an API server that install different packages - make them separate container-magic projects rather than trying to build multiple targets from one cm.yaml.

Projects that share code can use [workspace symlinks](#workspace-symlinks). Place symlinks in each project's workspace pointing to the shared code. Container-magic will bind-mount the targets during development and copy them into the image for production.

Each stage also supports:

- `distro` - Override the auto-detected distribution family. Sets package manager, user creation style, and interactive shell in one field. Inherited by child stages. Useful when using a custom or locally-built base image whose name doesn't match a known distribution. Supported values: `alpine`, `debian`, `ubuntu`, `fedora`, `centos`, `rhel`, `rocky`, `alma`. Unrecognised values warn and default to Debian settings.
- `package_manager` - Override the package manager (`apt`, `apk`, or `dnf`). Takes precedence over `distro` if both are set.

Package installation uses the command builder step syntax. The command name determines which package manager is used. Container-optimised defaults (flags, cleanup) are applied automatically - see [Package Installation](build-steps.md#package-installation) for details.

```yaml
# Debian / Ubuntu
steps:
  - apt-get:
      install:
        - curl
        - git

# Alpine
steps:
  - apk:
      add:
        - curl
        - git

# Fedora / CentOS
steps:
  - dnf:
      install:
        - curl
        - git

# Python pip
steps:
  - pip:
      install:
        - requests
        - numpy
```

You can use any image from Docker Hub as your base (e.g., `python:3.11`, `ubuntu:22.04`, `pytorch/pytorch`, `nvidia/cuda:12.4.0-runtime-ubuntu22.04`).

## Commands

Define custom commands that work in both dev and prod:

```yaml
commands:
  train:
    command: python workspace/train.py
    description: Train model
    env:
      CUDA_VISIBLE_DEVICES: "0"

  serve:
    command: python -m http.server 8000
    description: Start dev server
    ports:
      - "8000:8000"
```

**Command options:**

| Option | Description |
|--------|-------------|
| `command` | The command to run (supports multi-line via YAML `\|` syntax) |
| `description` | Help text |
| `env` | Environment variables passed to the container |
| `ports` | Ports to publish (`host:container` format, generates `--publish` flags) |
| `ipc` | IPC namespace mode override for this command (e.g. `host`, `shareable`) |
| `mounts` | Named bind mounts (see [Mounts](mounts.md)) |

**Development:**

- `cm run train` - from anywhere in your repository

**Production:**

- `./run.sh train` - via run.sh

### Mounts

Commands can declare named mounts that bind host paths into the container at
runtime. See [Mounts](mounts.md) for full documentation.

```yaml
commands:
  process:
    command: python process.py
    mounts:
      data:
        mode: ro
        prefix: "--data "
      results:
        mode: rw
        prefix: "--output "
```

At runtime, provide values using `name=/path` syntax:

```bash
cm run process data=/recordings/set-01 results=/tmp/output
```

Mounts are optional. If you don't provide a mount value, it isn't created.
Container-magic doesn't enforce whether a mount is required - that's up to
your application.

### Passing Extra Flags

All commands accept additional arguments which are appended to the command:

```bash
cm run train --epochs 10 --lr 0.001
# Runs: python workspace/train.py --epochs 10 --lr 0.001

./run.sh train --epochs 10
# Same in production
```

## Build Script

The standalone `build.sh` script builds the production target by default:

```bash
./build.sh              # Builds production stage, tagged as 'latest'
./build.sh --tag v1.0   # Builds production stage, tagged as 'v1.0'
./build.sh --help       # Shows available options
```

**Options:**

- `--tag TAG` - override the image tag (default: `latest`)
- `--uid UID` - override the user UID
- `--gid GID` - override the user GID

## Build Context

Container-magic manages `.dockerignore` with a deny-by-default policy. Only
the workspace directory and cached assets are included in the Docker build
context; everything else (outputs, data folders, `.git`, scripts) is excluded
automatically.

The managed section is regenerated by `cm init` and `cm update`:

```
# container-magic:begin (generated, do not edit)
*
!workspace/
!workspace/**
!.cm-cache/
!.cm-cache/**
# container-magic:end
```

If you rename the workspace directory, `cm update` rewrites the allowlist.
User additions above or below the markers are preserved.

If a build step needs a file outside the workspace (rare), add a negation
below the managed section:

```
# container-magic:end

# My additions
!config.yaml
```
