# User Handling

Container-magic handles users differently for development and production.

## The `names.user` Field

Every `cm.yaml` must include `names.user`. This field controls the container's user identity:

- **`user: root`** - the container runs as root. No user creation is needed, and the `create: user` and `become: user` steps are not available (both produce errors, since root already exists and containers default to root).
- **`user: <name>`** (e.g. `nonroot`, `appuser`) - a custom user will be created by `create: user` steps. The `become: user` step switches to this user, and `copy` steps gain automatic `--chown` when user context is active.

The `cm init` scaffold sets `user: nonroot` by default and places `create: user` and `become: user` in the base stage.

## Development (`just build` and `just run`)

When you run `just build` or `just run`, the container is built and run as **your current system user**:

```bash
# The build recipe captures:
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

The `create: user` step in the Dockerfile uses `ARG` values for the username and UID/GID, so development builds pass your host identity while production builds use the defaults.

## Production (`./build.sh` and `./run.sh`)

The standalone production scripts use the user defined by `names.user` in your config, created by the `create: user` step:

```yaml
names:
  project: my-project
  user: nonroot             # This user is baked into the image

stages:
  base:
    from: python:3.11-slim
    steps:
      - create: user        # Creates 'nonroot' with uid=1000, gid=1000
      - become: user        # Switches to 'nonroot'
```

The user is always created with uid/gid 1000. For rare cases where the host uid/gid must differ, `build.sh` accepts `--uid` and `--gid` flags.

If `names.user` is `root` (and therefore no `create: user` step exists), the container runs as root with UID 0.

!!! note
    When `names.user` is `root`, the `run.sh` script still works correctly. Commands execute with root privileges -- this is the default Docker/Podman behaviour (no `USER` directive means root).

## Copy Ownership

The lowercase `copy` step interacts with user context to control file ownership:

| Step | Behaviour |
|------|-----------|
| `copy` (lowercase) | Adds `--chown=<username>:<username>` when `become` is active for a non-root user. Plain `COPY` otherwise. |
| `COPY` (uppercase) | Raw Dockerfile passthrough, no automatic ownership. |

User context is inherited from parent stages -- if a parent ends with `become: user`, child stages start with user context active.

### Example: Mixed Ownership

```yaml
names:
  project: my-project
  user: nonroot

stages:
  base:
    from: python:3.11-slim
    steps:
      - create: user
      - copy: default.conf /etc/nginx/nginx.conf  # Root-owned (before become)
      - become: user
      - copy: workspace                            # User-owned (context-aware)
```

See [Build Steps](build-steps.md#4-copy) for full details on the copy step.

## Default Scaffold

When you run `cm init`, the generated `cm.yaml` places `create: user` and `become: user` in the base stage. This means child stages (development, production) inherit the user context automatically:

```yaml
names:
  project: my-project
  user: nonroot

stages:
  base:
    from: python:3.11-slim
    steps:
      - create: user
      - become: user

  development:
    from: base           # Inherits user context from base

  production:
    from: base
    steps:
      - copy: workspace  # Automatically gets --chown because base ends with become: user
```
