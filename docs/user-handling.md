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

The standalone production scripts use the user configuration from your `cm.yaml`:

```yaml
user:
  production:
    name: appuser      # This user is baked into the image
    uid: 1000
    gid: 1000
```

If no `user.production` is defined, **the container runs as root** (`root` user with UID 0).

!!! note
    When no user is configured, the `run.sh` script still works correctly. Commands execute with root privileges — this is the default Docker/Podman behaviour (no `USER` directive means root).

## Copy Ownership

The copy steps interact with user context to control file ownership:

| Step | Behaviour |
|------|-----------|
| `copy` | Adds `--chown` when `become_user` is active, plain `COPY` otherwise |
| `copy_as_user` | Always adds `--chown=${USER_UID}:${USER_GID}` |
| `copy_as_root` | Never adds `--chown` |
| `COPY` (uppercase) | Raw Dockerfile passthrough, no automatic ownership |

User context is inherited from parent stages — if a parent ends with `become_user`, child stages start with user context active.

### Example: Mixed Ownership

```yaml
user:
  production:
    name: appuser

stages:
  production:
    from: base
    steps:
      - create_user
      - copy_as_user config/app.conf /home/appuser/.config/  # User-owned
      - copy_as_root config/system.conf /etc/app/            # Root-owned
      - become_user
      - copy app /home/appuser/app                           # User-owned (context-aware)
```

See [Build Steps](build-steps.md#8-copy) for full details on each copy variant.
