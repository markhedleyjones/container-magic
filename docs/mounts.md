# Mounts

Mounts let commands declare host directories or files that should be bound into
the container at runtime. They handle the boundary between host and container.
Anything already inside the container (workspace code, configs baked into the
image) does not need a mount.

## Configuration

Each mount has a name and a mode. The mode is always required.

**Shorthand form** - when no prefix is needed:

```yaml
commands:
  process:
    command: scripts/process.sh
    mounts:
      data: ro
      results: rw
```

**Full form** - when the mount path should be passed to the command via a prefix:

```yaml
commands:
  process:
    command: scripts/process.sh
    mounts:
      data:
        mode: ro
        prefix: "--data "
      results:
        mode: rw
        prefix: "--output "
```

Both forms can be mixed in the same block.

## Modes

| Mode | Permissions | Volume flag | Use for |
|------|-------------|-------------|---------|
| `ro` | Read-only | `:ro,z` | Input data, models, config files |
| `rw` | Read-write | `:z` | Output directories, working directories |

`rw` means the container can both read from and write to the mounted path.

## Runtime usage

Provide mount values at runtime using `name=/path` syntax:

```bash
cm run process data=/recordings/set-01 results=/tmp/output
# Mounts /recordings/set-01 at /mnt/data/set-01 (read-only)
# Mounts /tmp/output at /mnt/results (read-write)
# Runs: scripts/process.sh --data /mnt/data/set-01 --output /mnt/results
```

Production works the same way:

```bash
./run.sh process data=/recordings/set-01 results=/tmp/output
```

### Mounts are optional

If you don't provide a value for a mount, it isn't created. Container-magic
doesn't enforce whether a mount is required - that's up to your application.
A command with three declared mounts can be called with zero, one, two, or all
three.

### Container paths

- `ro` mounts: `/mnt/<name>/<basename>` - preserves the original filename
- `rw` mounts: `/mnt/<name>/` - the directory itself

A manifest file at `/run/cm/mounts` records the host-to-container path mappings
for any active mounts.

## Patterns

### Mixed mount and workspace paths

A command can use mounts for external data while also reading from the workspace
(which is baked into the image or bind-mounted in development). Not everything
needs to be a mount.

```yaml
commands:
  process:
    command: scripts/process.sh
    mounts:
      data:
        mode: ro
        prefix: "--data "
      results:
        mode: rw
        prefix: "--results "
```

The script reads a config from the workspace and uses the mounted paths for
data and output:

```bash
#!/usr/bin/env bash
# --data and --results come from mounts
# config is resolved from the workspace (already in the container)
CONFIG="$WORKSPACE/configs/default.yaml"
python process.py --config "$CONFIG" "$@"
```

### Discovery pattern

When a command needs to find files within a directory tree (for example, finding
the most recent recording), mount the parent directory and let the script search:

```yaml
commands:
  latest:
    command: scripts/process_latest.sh
    mounts:
      recordings:
        mode: ro
        prefix: "--dir "
```

```bash
cm run latest recordings=/data/recordings
# The script finds the newest file in /mnt/recordings/ itself
```

The mount doesn't have to point to a specific file - it can be any level of the
directory tree.

### Convenience wrappers

If your commands accept short names that map to known paths, wrap them in a
script or Makefile:

```bash
#!/usr/bin/env bash
# slam-run.sh - convenience wrapper
BAG_DIR="/data/bags"
OUTPUT_DIR="/data/output"
cm run slam bag="${BAG_DIR}/$1" results="${OUTPUT_DIR}" "${@:2}"
```

```bash
./slam-run.sh airy-indoor-01 default
# Expands to: cm run slam bag=/data/bags/airy-indoor-01 results=/data/output default
```

The mounts system provides the underlying mechanism. Convenience is added on
top with standard shell scripting.
