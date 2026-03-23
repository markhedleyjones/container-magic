# User Handling

Container-magic handles users differently for development and production.

## The `names.user` Field

Every `cm.yaml` must include `names.user`. This field controls the container's user identity:

- **`user: root`** - the container runs as root. No user creation is needed, and the `create: user` and `become: user` steps are not available (both produce errors, since root already exists and containers default to root).
- **`user: <name>`** (e.g. `nonroot`, `appuser`) - a custom user is automatically created at the start of each stage that uses an external base image. At the end of each leaf stage (development, production, or any custom target stage), the container switches to this user. No explicit `create: user` or `become: user` steps are needed.

The `cm init` scaffold sets `user: nonroot` by default.

!!! info "How the container user is resolved"

    === "Development"

        The container runs as **your host user** (matching UID, GID, and
        home directory). File permissions work seamlessly between host and
        container.

    === "Production"

        The container runs as the user defined by `names.user`, with
        uid/gid 1000. Override with `./build.sh --uid` and `--gid` if
        needed.

## Development (`cm build` and `cm run`)

When you run `cm build`, the container is built as **your current system user**:

- Your UID, GID, username, and home directory are passed as build args
- You run commands as yourself (same UID/GID as your host)
- Your home directory is mapped into the container
- File permissions are correct (no permission issues)
- You can edit code on the host and run it in the container seamlessly

The user creation step in the Dockerfile uses `ARG` values for the username and UID/GID, so development builds pass your host identity while production builds use the defaults.

## Production (`./build.sh` and `./run.sh`)

The standalone production scripts use the user defined by `names.user`:

```yaml
names:
  image: my-project
  user: nonroot             # This user is baked into the image

stages:
  base:
    from: python:3.11-slim

  development:
    from: base

  production:
    from: base
```

The user is automatically created with uid/gid 1000. For rare cases where the host uid/gid must differ, `build.sh` accepts `--uid` and `--gid` flags.

If `names.user` is `root`, the container runs as root with UID 0.

!!! note
    When `names.user` is `root`, the `run.sh` script still works correctly. Commands execute with root privileges.

## Workspace Ownership in Production

In production, the workspace is copied into the image as root-owned files. This means the application code is immutable - the running user cannot modify it. The implicit `USER` switch happens after the workspace copy, so the container process runs as the configured user but cannot write to the workspace.

If you need user-owned workspace files in production (e.g. for a writable data directory), use explicit `become: user` before `copy: workspace`:

```yaml
production:
  from: base
  steps:
    - become: user
    - copy: workspace          # Gets --chown, user-owned
```

## Copy Ownership

The lowercase `copy` step interacts with user context to control file ownership:

| Step | Behaviour |
|------|-----------|
| `copy` (lowercase) | Adds `--chown=<username>:<username>` when `become` is active for a non-root user. Plain `COPY` otherwise. |
| `COPY` (uppercase) | Raw Dockerfile passthrough, no automatic ownership. |

### Example: Mixed Ownership

```yaml
names:
  image: my-project
  user: nonroot

stages:
  base:
    from: python:3.11-slim
    steps:
      - copy: default.conf /etc/nginx/nginx.conf  # Root-owned (no become active)
      - become: user
      - copy: app.conf /home/nonroot/.config/      # User-owned (become active)
```

See [Build Steps](build-steps.md#4-copy) for full details on the copy step.

## Explicit User Steps

For most projects, implicit user handling is all you need. Explicit `create: user` and `become: user` steps are available for cases where you need fine-grained control:

- Controlling exactly where in the step sequence the user is created
- Switching to a different user mid-stage (e.g. `become: www-data`)
- Placing `become: user` before `copy: workspace` to get user-owned files

When any stage has an explicit `create: user`, implicit user creation is disabled for all stages. This avoids double-creation.

## Default Scaffold

When you run `cm init`, the generated `cm.yaml` relies on implicit user handling:

```yaml
names:
  image: my-project
  user: nonroot

stages:
  base:
    from: python:3.11-slim

  development:
    from: base

  production:
    from: base
```

The user is automatically created in the base stage, and leaf stages (development, production) automatically switch to the configured user at the end.
