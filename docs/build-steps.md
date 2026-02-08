# Build Steps

The `steps` field in each stage defines how the image is constructed. Container-magic provides built-in steps for common tasks, and supports custom Dockerfile commands for advanced use cases.

## Built-in Steps

### 1. `install_system_packages`

Installs system packages using the distribution's package manager (APT, APK, or DNF).

**Requires:** `packages.apt`, `packages.apk`, or `packages.dnf` defined

```yaml
stages:
  base:
    from: ubuntu:24.04
    packages:
      apt:
        - curl
        - git
        - build-essential
    steps:
      - install_system_packages
```

**Generated Dockerfile:** Runs `apt-get update && apt-get install` (with cleanup)

---

### 2. `install_pip_packages`

Installs Python packages using pip.

**Requires:** `packages.pip` defined

```yaml
stages:
  base:
    from: python:3.11-slim
    packages:
      pip:
        - requests
        - pytest
        - numpy
    steps:
      - install_pip_packages
```

**Generated Dockerfile:** Runs `pip install --no-cache-dir`

---

### 3. `create_user`

Creates a non-root user account for running the application.

**Requires:** `user.production` defined in config (with at least `name` field)

**Field defaults:**

- `uid`: 1000 (if not specified)
- `gid`: 1000 (if not specified)
- `home`: `/home/${name}` (if not specified)

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

### 4. `become_user`

Switches the current user context from root to the configured non-root user. Also sets the user context for subsequent `copy` steps.

**Requires:** `create_user` step in same or parent stage, user config defined

**Alias:** `switch_user` (deprecated, still works)

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

---

### 5. `become_root`

Switches user context back to root (if needed after `become_user`).

**Requires:** `become_user` step executed previously

**Alias:** `switch_root` (deprecated, still works)

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

---

### 6. `copy_cached_assets`

Copies pre-downloaded assets into the image (avoids re-downloading during builds).

**Requires:** `cached_assets` defined in stage

**Generated Dockerfile:** Copies files from build cache into image with `--chown` applied automatically if a user is configured

!!! note
    Must be explicitly added to `steps` to copy assets into image. Assets are downloaded but not used if this step is missing.

See [Cached Assets](cached-assets.md) for detailed usage and configuration.

---

### 7. `copy_workspace`

Copies the entire workspace directory into the image (typically for production builds).

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

!!! note
    This is the automatic default step for the production stage if not specified.

---

### 8. `copy`

User-context-aware file copy. Behaves like Docker's `COPY` but automatically adds `--chown=${USER_UID}:${USER_GID}` when `become_user` is active. Lowercase = smart abstraction, uppercase `COPY` = raw Dockerfile passthrough.

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

---

### 9. `copy_as_user`

Copies files with user ownership regardless of the current user context. Always adds `--chown=${USER_UID}:${USER_GID}`.

```yaml
steps:
  - create_user
  - copy_as_user config/app.conf /home/appuser/.config/
  - become_user
```

**Use case:** Set up user-owned files while still running as root, before switching context.

---

### 10. `copy_as_root`

Copies files with root ownership regardless of the current user context. Never adds `--chown`.

```yaml
steps:
  - create_user
  - become_user
  - copy_as_root config/system.conf /etc/app/
  - copy app /home/appuser/app
```

**Use case:** Copy root-owned system files without needing to switch context back and forth. Equivalent to uppercase `COPY` but keeps your steps in the container-magic vocabulary.

---

## Custom Dockerfile Commands

Any string that doesn't match a built-in keyword is treated as a custom Dockerfile command.

```yaml
stages:
  base:
    from: ubuntu:24.04
    packages:
      apt:
        - python3
        - python3-pip
    steps:
      - install_system_packages
      - install_pip_packages
      - RUN pip install --break-system-packages requests
      - ENV APP_MODE=production
      - WORKDIR /app
      - LABEL maintainer="you@example.com"
```

**Supported Dockerfile instructions:**

- `RUN` — Execute commands
- `ENV` — Set environment variables
- `WORKDIR` — Change working directory
- `COPY` / `ADD` — Copy files (uppercase passes through as-is; use lowercase `copy` for automatic `--chown`)
- `EXPOSE` — Expose ports
- `LABEL` — Add metadata
- Any other valid Dockerfile instruction

### Variable Substitution

You can reference container-magic variables in custom steps:

- `${WORKSPACE}` — Workspace directory path
- `${WORKDIR}` — Working directory
- `${USER_NAME}` — Non-root user name (if configured)
- `${USER_UID}` / `${USER_GID}` — User IDs

## Using `$WORKSPACE` in Container Scripts

The `$WORKSPACE` environment variable is automatically set inside every container and points to your workspace directory. Scripts can rely on it without any extra setup.

```bash
# Good - uses $WORKSPACE variable set at build time
bash $WORKSPACE/scripts/commands.sh preprocess

# Less ideal - manual path construction
bash /home/user/workspace/scripts/commands.sh preprocess
```

**In custom commands:**

```yaml
commands:
  process:
    command: python $WORKSPACE/scripts/process.py
    description: Process workspace data
```

**In Dockerfile steps:**

```yaml
stages:
  base:
    from: python:3.11
    steps:
      - copy_workspace
      - RUN python ${WORKSPACE}/setup.py build
      - RUN ${WORKSPACE}/scripts/init.sh
```

## Default Step Behaviour

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

## Step Ordering Rules

1. **Steps execute in order** — left to right, top to bottom
2. **User creation before switching** — `create_user` must come before `become_user`
3. **Packages before custom commands** — install system/pip packages before using them
4. **Assets before commands** — copy cached assets before commands that use them
5. **User switching for security** — switch to non-root after setup, use `copy_as_root` or `become_root` if needed for privileged ops

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

## Common Patterns

### Multi-stage with shared base

```yaml
stages:
  base:
    from: python:3.11-slim
    packages:
      apt:
        - git
        - build-essential
      pip:
        - setuptools
    steps:
      - install_system_packages
      - install_pip_packages

  development:
    from: base
    packages:
      pip: [pytest, black, mypy]  # Inline style works too

  production:
    from: base
    packages:
      pip:
        - gunicorn
    steps:
      - create_user
      - become_user
      - copy_workspace
```

### Using cached assets for models

```yaml
stages:
  base:
    from: pytorch/pytorch:latest
    packages:
      pip:
        - transformers
    cached_assets:
      - url: https://huggingface.co/bert-base-uncased/resolve/main/model.safetensors
        dest: /models/bert.safetensors
    steps:
      - install_pip_packages
      - copy_cached_assets
      - RUN python -c "from transformers import AutoModel; AutoModel.from_pretrained('/models')"
```

### Custom build steps with environment

```yaml
stages:
  base:
    from: node:18-alpine
    steps:
      - ENV NODE_ENV=production
      - ENV PATH=/app/node_modules/.bin:$PATH
      - RUN npm install --global yarn
```

## Validation Rules

| Rule | Error | Solution |
|------|-------|----------|
| `become_user` without `create_user` | Warning | Add `create_user` step before `become_user` |
| `create_user` without user config | Error | Define `user.production` in config |
| `become_user` without user config | Error | Define `user.production` in config |
| `cached_assets` without `copy_cached_assets` | Warning | Add `copy_cached_assets` step to use assets |
