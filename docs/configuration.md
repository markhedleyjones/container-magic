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

Run `cm update` after editing `cm.yaml` to regenerate the Dockerfile and scripts. `cm build` also regenerates automatically before building.

## Backend

```yaml
backend: docker      # docker, podman, or auto (default: auto, omit for auto)
```

When set to `auto` (the default), container-magic will use whichever of `podman` or `docker` is available, preferring `podman`.

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

If a `.env` file exists in the project root, its variables are automatically passed to the container via `--env-file`. No configuration is needed.

```
# .env
DATABASE_URL=postgres://localhost/mydb
API_KEY=secret123
```

This works in both development (`cm run`) and production (`run.sh`). If no `.env` file is present, nothing happens.

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

Development containers are named `<image-name>-development` and production containers are named `<image-name>`. If a container with the same name is already running, `cm run` will exec into the existing container instead of starting a new one.

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
