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

- `user: root` - the container runs as root. No user creation is needed (or allowed - `create: user` and `become: user` are errors when `user` is `root`).
- `user: <name>` (any other value, e.g. `nonroot`, `appuser`) - a custom user will be created by `create: user` steps and referenced by `become: user` steps. See [User Handling](user-handling.md) for details.

Generated files are automatically regenerated when your config changes. To disable this, set `auto_update: false` at the root level of `cm.yaml`.

## Backend

```yaml
backend: docker      # docker, podman, or auto (default: auto, omit for auto)
```

When set to `auto` (the default), container-magic will use whichever of `podman` or `docker` is available, preferring `podman`.

## Runtime

```yaml
runtime:
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

- `shareable` - allow other containers to share this container's IPC namespace
- `container:<name>` - join another container's IPC namespace
- `host` - use the host's IPC namespace
- `private` - container's own private IPC namespace (default)

Per-command overrides are supported via the `ipc` field on individual commands.

### Container Names

Development containers are named `<image-name>-development` and production containers are named `<image-name>`. If a container with the same name is already running, `just run` will exec into the existing container instead of starting a new one. Use `just stop` to stop a running container and `just clean` to remove it.

### Detached Mode

Containers can be started in the background:

- **Justfile:** `just run --detach <command>` or `just run -d <command>`
- **run.sh:** `./run.sh --detach <command>` or `./run.sh -d <command>`

To stop a detached container:

- **Justfile:** `just stop`
- **run.sh:** `./run.sh --stop`

## Stages

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

Each stage also supports:

- `package_manager` - Override the auto-detected package manager (`apt`, `apk`, or `dnf`). Normally inferred from the base image.
- `shell` - Override the default shell for the stage. Normally inferred from the base image.

Package installation uses the command builder step syntax. The command name determines which package manager is used. Container-optimised defaults (flags, cleanup) are applied automatically -- see [Package Installation](build-steps.md#package-installation) for details.

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

- **`standalone: false`** (default) - Command available via `just <command>` and `./run.sh <command>` only
- **`standalone: true`** - Also generates a dedicated `<command>.sh` script for direct execution

**Development:**

- `just train` - from anywhere in your repository

**Production (standalone: false):**

- `./run.sh train` - only way to run

**Production (standalone: true):**

- `./run.sh deploy` - via run.sh
- `./deploy.sh` - dedicated standalone script

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
  default_target: production  # Optional: stage to build (default: production)
```

The `build.sh` script builds the configured target stage:

```bash
./build.sh              # Builds production stage, tagged as 'latest'
./build.sh --tag v1.0   # Builds production stage, tagged as 'v1.0'
./build.sh --help       # Shows available options
```

**Options:**

- `--tag TAG` - override the image tag (default: `latest`)
- `--uid UID` - override the user UID
- `--gid GID` - override the user GID
