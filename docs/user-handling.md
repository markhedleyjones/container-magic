# User Handling

Container-magic handles users differently for development and production.

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

## Production (`./build.sh` and `./run.sh`)

The standalone production scripts use the user defined by the `create_user` step in your build stages:

```yaml
stages:
  base:
    from: python:3.11-slim
    steps:
      - create_user: nonroot    # This user is baked into the image
```

If no `create_user` step is used, **the container runs as root** (`root` user with UID 0).

For custom uid/gid, use the extended form:

```yaml
stages:
  base:
    from: python:3.11-slim
    steps:
      - create_user:
          name: appuser
          uid: 2000
          gid: 2000
```

!!! note
    When no user is created, the `run.sh` script still works correctly. Commands execute with root privileges - this is the default Docker/Podman behaviour (no `USER` directive means root).

## Copy Ownership

The `copy` step interacts with user context to control file ownership:

| Step | Behaviour |
|------|-----------|
| `copy` | Adds `--chown=<username>:<username>` when `become` is active, plain `COPY` otherwise |
| `COPY` (uppercase) | Raw Dockerfile passthrough, no automatic ownership |

User context is inherited from parent stages - if a parent ends with `become: nonroot`, child stages start with user context active.

### Example: Mixed Ownership

```yaml
stages:
  production:
    from: base
    steps:
      - create_user: app
      - copy config/system.conf /etc/app/            # Root-owned (before become)
      - become: app
      - copy app /home/app/app                       # User-owned (context-aware)
```

See [Build Steps](build-steps.md#4-copy) for full details on the copy step.
