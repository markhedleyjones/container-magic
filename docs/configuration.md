# Configuration

Container-magic is configured through a single YAML file (`cm.yaml` or `container-magic.yaml`).

## Project

```yaml
project:
  name: my-project      # Required: image name
  workspace: workspace  # Required: directory with your code
```

Generated files are automatically regenerated when your config changes. To disable this, set `auto_update: false` under `project:`.

## Runtime

```yaml
runtime:
  backend: auto      # docker, podman, or auto
  privileged: false  # privileged mode
  network_mode: host # host, bridge, or none (optional)
  ipc: shareable     # IPC namespace mode (optional)
  features:
    - gpu              # NVIDIA GPU
    - display          # X11/Wayland
    - audio            # PulseAudio/PipeWire
    - aws_credentials  # AWS credential forwarding
  volumes:
    - /host/path:/container/path        # bind mount
    - /host/path:/container/path:ro     # read-only bind mount
  devices:
    - /dev/video0:/dev/video0           # device passthrough
```

### IPC Namespace

The `ipc` field sets the IPC namespace mode for containers (`--ipc` flag). Common values:

- `shareable` — allow other containers to share this container's IPC namespace
- `container:<name>` — join another container's IPC namespace
- `host` — use the host's IPC namespace
- `private` — container's own private IPC namespace (default)

Per-command overrides are supported via the `ipc` field on individual commands.

### Container Names

Development containers are named `<project-name>-development` and production containers are named `<project-name>`. If a container with the same name is already running, `just run` will exec into the existing container instead of starting a new one. Use `just stop` to stop a running container and `just clean` to remove it.

### Detached Mode

Containers can be started in the background:

- **Justfile:** `just run --detach <command>` or `just run -d <command>`
- **run.sh:** `./run.sh --detach <command>` or `./run.sh -d <command>`

To stop a detached container:

- **Justfile:** `just stop`
- **run.sh:** `./run.sh --stop`

## User

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

See [User Handling](user-handling.md) for more detail on how users work in development vs production.

## Stages

```yaml
stages:
  base:
    from: python:3.11-slim    # Any Docker Hub image
    packages:
      apt:
        - git
        - curl
      pip:
        - numpy
        - pandas
    env:
      VAR: value

  development:
    from: base                # Inherit from base
    packages:
      pip:
        - pytest

  production:
    from: base
```

Each stage also supports:

- `package_manager` - Override the auto-detected package manager (`apt`, `apk`, or `dnf`). Normally inferred from the base image.
- `shell` - Override the default shell for the stage. Normally inferred from the base image.

The package field name determines which package manager is used: `apt` uses `apt-get install`, `apk` uses `apk add`, `dnf` uses `dnf install`. Use the field that matches your base image:

```yaml
# Alpine
packages:
  apk: [curl, git]

# Fedora / CentOS
packages:
  dnf: [curl, git]
```

`cm init` scaffolds the correct field automatically based on the base image you specify.

!!! tip "Inline lists"
    Package lists can also be written inline for brevity: `pip: [pytest, black, mypy]`. Both styles are valid YAML — use whichever is clearer for the length of your list.

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

| Option | Description |
|--------|-------------|
| `command` | The command to run (supports multi-line via YAML `\|` syntax) |
| `description` | Help text shown in Justfile |
| `args` | Positional arguments (see below) |
| `env` | Environment variables passed to the container |
| `ports` | Ports to publish (`host:container` format, generates `--publish` flags) |
| `ipc` | IPC namespace mode override for this command (e.g. `host`, `shareable`) |
| `standalone` | Generate a dedicated `<command>.sh` script |

The `standalone` flag (default: `false`) controls script generation:

- **`standalone: false`** (default) — Command available via `just <command>` and `./run.sh <command>` only
- **`standalone: true`** — Also generates a dedicated `<command>.sh` script for direct execution

**Development:**

- `just train` — from anywhere in your repository

**Production (standalone: false):**

- `./run.sh train` — only way to run

**Production (standalone: true):**

- `./run.sh deploy` — via run.sh
- `./deploy.sh` — dedicated standalone script

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

| Option | Description |
|--------|-------------|
| `type` | One of: `file`, `directory`, `string`, `int`, `float` |
| `description` | Help text for the argument |
| `default` | Default value (makes the argument optional) |
| `readonly` | For file/directory types: validate existence (default: `true`) |
| `mount_as` | For file/directory types: mount at this container path |

**Generated Just recipe:**

```
process input output="" *args:
```

Required arguments come first, followed by optional arguments with their defaults. The `{arg_name}` placeholders in the command are substituted with the actual values (or mount paths if `mount_as` is specified).

### Passing Extra Flags

All commands include `*args` which captures any additional arguments (including flags) and appends them to the command:

```bash
just process input.txt --verbose --dry-run
# Runs: python process.py input.txt --verbose --dry-run

just process input.txt output.txt --format=json
# Runs: python process.py input.txt output.txt --format=json
```

### File Mounting Example

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

When `mount_as` is specified, the host file is mounted into the container at that path, and the command uses the container path.

## Build Script

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

**Image tagging:**

- Production stage is tagged as `<project-name>:latest`
- All other stages are tagged as `<project-name>:<stage-name>`
