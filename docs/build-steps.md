# Build Steps

The `steps` field in each stage defines how the image is constructed. Container-magic provides built-in steps for common tasks, and supports custom Dockerfile commands for advanced use cases.

## Built-in Steps

### 1. `install_system_packages`

Installs system packages. Each field maps directly to its package manager — `packages.apt` runs `apt-get install`, `packages.apk` runs `apk add`, `packages.dnf` runs `dnf install`. Use the field that matches your base image.

**Requires:** At least one of `packages.apt`, `packages.apk`, or `packages.dnf` defined

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

For Alpine images, use `apk:` instead of `apt:`:

```yaml
stages:
  base:
    from: alpine:latest
    packages:
      apk:
        - curl
        - git
    steps:
      - install_system_packages
```

For Fedora/CentOS images, use `dnf:`:

```yaml
stages:
  base:
    from: fedora:latest
    packages:
      dnf:
        - curl
        - git
    steps:
      - install_system_packages
```

Each populated field generates its own install command independently. `cm init` scaffolds the correct field based on the base image.

**Generated Dockerfile:** Runs the install command for each populated field (e.g., `apt-get update && apt-get install` with cleanup)

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

### Copying from other stages (`--from=`)

All three copy variants support Docker's `--from=<stage>` syntax for copying artefacts between stages that don't inherit from each other. This is useful for multi-stage builds where a heavy builder stage compiles dependencies and a lightweight runtime stage copies only the installed artefacts:

```yaml
stages:
  builder:
    from: ubuntu:24.04
    packages:
      apt: [build-essential, cmake]
    steps:
      - install_system_packages
      - /tmp/build_deps.sh

  base:
    from: ubuntu:24.04
    steps:
      - install_system_packages
      - copy_as_root --from=builder /usr/local/lib /usr/local/lib
      - copy_as_root --from=builder /usr/local/include /usr/local/include
      - ldconfig
```

**Generated Dockerfile:**

```dockerfile
COPY --from=builder /usr/local/lib /usr/local/lib
COPY --from=builder /usr/local/include /usr/local/include
```

With `copy_as_user`, `--chown` is added automatically:

```yaml
- copy_as_user --from=builder /opt/app /home/appuser/app
```

```dockerfile
COPY --chown=${USER_UID}:${USER_GID} --from=builder /opt/app /home/appuser/app
```

The `--from=` argument should reference a stage name defined in the same `cm.yaml`. The stage doesn't need to be a parent — it can be any stage in the build.

---

## Custom Dockerfile Commands

Any string that doesn't match a built-in keyword is treated as a custom Dockerfile command. Each custom step becomes one Dockerfile instruction and therefore one Docker layer.

### Implicit RUN Wrapping

If a step starts with an **uppercase Dockerfile instruction** (`RUN`, `ENV`, `COPY`, `WORKDIR`, `ADD`, `EXPOSE`, `LABEL`, `USER`, `VOLUME`), it passes through to the Dockerfile as-is. Otherwise, container-magic automatically wraps the step with `RUN`:

```yaml
steps:
  # These pass through as-is (uppercase Dockerfile instruction)
  - RUN pip install requests
  - ENV APP_MODE=production
  - WORKDIR /app
  - LABEL maintainer="you@example.com"

  # These are automatically wrapped with RUN
  - pip install requests          # → RUN pip install requests
  - apt-get update                # → RUN apt-get update
  - echo "hello"                  # → RUN echo "hello"
```

This means you can write steps concisely — just write the command and container-magic adds the `RUN` for you.

### Multi-line Steps

Use a YAML `|` block to combine multiple commands into a **single `RUN` instruction** (and therefore a single Docker layer). Lines are automatically joined with `&& \`:

```yaml
steps:
  - install_system_packages
  - |
    mkdir -p /opt/my_project/src
    cd /opt/my_project/src
    git clone --depth 1 https://github.com/example/repo.git
    cd repo
    cmake -B build
    cmake --build build
    cmake --install build
```

**Generated Dockerfile:**

```dockerfile
RUN mkdir -p /opt/my_project/src && \
    cd /opt/my_project/src && \
    git clone --depth 1 https://github.com/example/repo.git && \
    cd repo && \
    cmake -B build && \
    cmake --build build && \
    cmake --install build
```

This is particularly useful when commands share shell state — `cd` changes, sourced environments, and shell variables all persist across lines because everything runs in a single shell invocation. No need for a `bash -c '...'` wrapper.

**Example — building a ROS2 workspace:**

```yaml
steps:
  - install_system_packages
  - |
    mkdir -p /opt/ros_ws/src
    cd /opt/ros_ws/src
    git clone --depth 1 https://github.com/example/ros_package.git
    cd /opt/ros_ws
    . /opt/ros/jazzy/setup.sh
    colcon build
```

The `. /opt/ros/jazzy/setup.sh` (source) sets up the ROS environment, and `colcon build` on the next line can use it — because they're in the same `RUN`.

### Single-line vs Multi-line: Docker Layer Caching

Each step becomes one Docker layer. This gives you explicit control over caching:

**Separate steps** — each gets its own layer with independent caching:

```yaml
steps:
  - apt-get update                              # Layer 1
  - apt-get install -y cuda-toolkit-12-6        # Layer 2 (cached if layer 1 unchanged)
  - dpkg -i /tmp/some-package.deb               # Layer 3 (cached if layers 1-2 unchanged)
```

If only the third step changes, Docker reuses the cached layers for the first two. Good for iterating on later steps during development.

**Combined step** — everything in one layer, rebuilt together:

```yaml
steps:
  - |
    apt-get update
    apt-get install -y cuda-toolkit-12-6
    dpkg -i /tmp/some-package.deb
```

If anything changes, the entire layer rebuilds. Good for related commands that should always run together (like cloning a repo and building it).

**Rule of thumb:** combine commands that are logically one operation (clone + build, download + install). Keep unrelated operations as separate steps for better cache granularity.

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
