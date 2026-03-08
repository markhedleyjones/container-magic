# Build Steps

The `steps` field in each stage defines how the image is constructed. Container-magic provides built-in steps for common tasks, and supports custom Dockerfile commands for advanced use cases.

## Built-in Steps

### 1. `create`

Creates a user account in the container image.

**`create: user`** (keyword) - creates the user defined by `names.user` in your config. This is the primary way to set up a non-root user:

```yaml
names:
  project: my-project
  user: nonroot

stages:
  base:
    from: python:3.11-slim
    steps:
      - create: user  # creates 'nonroot' with uid=1000, gid=1000
```

The word `user` here is a keyword that resolves to whatever `names.user` is set to. It cannot be used when `names.user` is `root` -- root always exists in every container, so creating it is an error.

**`create: <literal>`** - creates a user with that exact name. Use this for secondary or additional users (e.g. service accounts), not for the primary container user:

```yaml
steps:
  - create: www-data-custom  # creates a literal user 'www-data-custom'
```

**`create: root`** is always an error. Root exists in every container image by default, so there is nothing to create.

**Defaults:**

- `uid`: 1000
- `gid`: 1000
- `home`: `/home/<username>`

For rare cases where the host uid/gid must differ, `build.sh` accepts `--uid` and `--gid` flags.

---

### 2. `become: <target>`

Switches the current user context. Sets the Dockerfile `USER` directive and controls whether subsequent `copy` steps add `--chown`.

**`become: user`** (keyword) - switches to the user defined by `names.user`. Cannot be used when `names.user` is `root`, because containers already run as root by default -- the step would be redundant.

**`become: root`** - switches back to root. Useful for privileged operations after a previous `become: user`.

**`become: <literal>`** - switches to any other user by name (e.g. `become: www-data`, `become: mysql`). Docker resolves the username against `/etc/passwd` at build time, so this works for users that already exist in the base image without needing a `create` step.

```yaml
names:
  project: my-project
  user: nonroot

stages:
  base:
    from: python:3.11-slim
    steps:
      - create: user
      - become: user                    # USER nonroot (resolved from names.user)
      - copy: entrypoint.sh /opt/       # COPY --chown=nonroot:nonroot ...
      - become: root                    # USER root
      - copy: default.conf /etc/nginx/  # COPY default.conf /etc/nginx/ (no --chown)
```

**Generated Dockerfile:** `USER <username>`

---

### 3. `copy: workspace`

The word `workspace` here is a keyword -- it resolves to the directory named by `names.workspace` (default: `workspace`). This copies the entire workspace directory into the image, typically for production builds. Context-aware -- adds `--chown` when `become` is active.

```yaml
stages:
  production:
    from: base
    steps:
      - become: user
      - copy: workspace
```

**Generated Dockerfile:**

- Without active user: `COPY workspace ${WORKSPACE}`
- With active user: `COPY --chown=<username>:<username> workspace ${WORKSPACE}`

!!! note
    This is the automatic default step for the production stage if no steps are specified.

A single-token `copy:` that does not match `names.workspace` is treated as a directory copy into the user's home, but container-magic will flag it:

- **Warning** if the workspace is never copied -- you probably meant `copy: workspace` or need to update `names.workspace`
- **Info** if the workspace is also copied -- you're copying an extra directory alongside the workspace, which is fine

This mirrors the `create:` step behaviour: the keyword form (`copy: workspace`) is the primary mechanism, and literal values are allowed but flagged to catch mistakes.

---

### 4. `copy`

User-context-aware file copy. Behaves like Docker's `COPY` but automatically adds `--chown=<username>:<username>` when `become` is active for a non-root user. Lowercase = smart abstraction, uppercase `COPY` = raw Dockerfile passthrough.

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
      - copy: config.yaml /etc/myservice/config.yaml
      - copy: scripts/init.sh /opt/init.sh
```

**Generated Dockerfile:**

```dockerfile
COPY --chown=nonroot:nonroot config.yaml /etc/myservice/config.yaml
COPY --chown=nonroot:nonroot scripts/init.sh /opt/init.sh
```

If the `copy` step appears before `become` or after `become: root`, it generates a plain `COPY` without `--chown`. User context is inherited from parent stages -- if a parent ends with `become: user`, child stages start with user context active.

### Copying from other stages (`--from=`)

The `copy` step supports Docker's `--from=<stage>` syntax for copying artefacts between stages that don't inherit from each other. This is useful for multi-stage builds where a heavy builder stage compiles dependencies and a lightweight runtime stage copies only the installed artefacts:

```yaml
stages:
  builder:
    from: ubuntu:24.04
    steps:
      - apt-get:
          install:
            - build-essential
            - cmake
      - /tmp/build_deps.sh

  base:
    from: ubuntu:24.04
    steps:
      - copy: --from=builder /usr/local/lib /usr/local/lib
      - copy: --from=builder /usr/local/include /usr/local/include
      - ldconfig
```

**Generated Dockerfile:**

```dockerfile
COPY --from=builder /usr/local/lib /usr/local/lib
COPY --from=builder /usr/local/include /usr/local/include
```

When `become` is active, `--chown` is added automatically:

```yaml
- become: user
- copy: --from=builder /usr/local/bin/myapp /usr/local/bin/myapp
```

```dockerfile
COPY --chown=user:user --from=builder /usr/local/bin/myapp /usr/local/bin/myapp
```

The `--from=` argument should reference a stage name defined in the same `cm.yaml`. The stage doesn't need to be a parent -- it can be any stage in the build.

---

### 5. `run`

Combines multiple commands into a single `RUN` instruction (one Docker layer). Commands are joined with `&& \` automatically:

```yaml
steps:
  - run:
      - mkdir -p /opt/app
      - cd /opt/app
      - git clone --depth 1 https://github.com/example/repo.git
      - cd repo
      - make install
```

Use this when commands are logically one operation -- for example, cloning a repository and building it. Shell state (`cd`, sourced environments, shell variables) persists across lines because everything runs in a single shell invocation.

For a single command, a bare string is simpler:

```yaml
steps:
  - echo "hello"     # becomes RUN echo "hello"
```

See [Multi-command Steps](#multi-command-steps) for more examples and [Docker Layer Caching](#docker-layer-caching) for when to combine vs separate commands.

---

### 6. `env`

Sets environment variables in the image. Accepts either a dict or a list:

**Dict form:**

```yaml
steps:
  - env:
      DATABASE_URL: postgresql://localhost/mydb
      API_KEY: test-key-123
      LOG_LEVEL: debug
```

**List form:**

```yaml
steps:
  - env:
      - DATABASE_URL: postgresql://localhost/mydb
      - API_KEY: test-key-123
      - LOG_LEVEL: debug
```

Both forms generate the same Dockerfile output. The list form also accepts `KEY=value` strings:

```yaml
steps:
  - env:
      - DATABASE_URL=postgresql://localhost/mydb
      - API_KEY=test-key-123
```

Consecutive `env` steps are automatically merged into a single `ENV` instruction in the Dockerfile.

**Generated Dockerfile:**

```dockerfile
ENV DATABASE_URL="postgresql://localhost/mydb" \
    API_KEY="test-key-123" \
    LOG_LEVEL="debug"
```

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
  - pip install requests          # becomes RUN pip install requests
  - apt-get update                # becomes RUN apt-get update
  - echo "hello"                  # becomes RUN echo "hello"
```

This means you can write steps concisely -- just write the command and container-magic adds the `RUN` for you.

### Multi-command Steps

Use `run:` with a list to combine multiple commands into a **single `RUN` instruction** (and therefore a single Docker layer). Commands are automatically joined with `&& \`:

```yaml
steps:
  - run:
      - mkdir -p /opt/my_project/src
      - cd /opt/my_project/src
      - git clone --depth 1 https://github.com/example/repo.git
      - cd repo
      - cmake -B build
      - cmake --build build
      - cmake --install build
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

This is particularly useful when commands share shell state -- `cd` changes, sourced environments, and shell variables all persist across lines because everything runs in a single shell invocation.

**Example -- building a ROS2 workspace:**

```yaml
steps:
  - run:
      - mkdir -p /opt/ros_ws/src
      - cd /opt/ros_ws/src
      - git clone --depth 1 https://github.com/example/ros_package.git
      - cd /opt/ros_ws
      - . /opt/ros/jazzy/setup.sh
      - colcon build
```

The `. /opt/ros/jazzy/setup.sh` (source) sets up the ROS environment, and `colcon build` on the next line can use it -- because they're in the same `RUN`.

### Docker Layer Caching

Each step becomes one Docker layer. This gives you explicit control over caching:

**Separate steps** -- each gets its own layer with independent caching:

```yaml
steps:
  - apt-get update                              # Layer 1
  - apt-get install -y cuda-toolkit-12-6        # Layer 2 (cached if layer 1 unchanged)
  - dpkg -i /tmp/some-package.deb               # Layer 3 (cached if layers 1-2 unchanged)
```

If only the third step changes, Docker reuses the cached layers for the first two. Good for iterating on later steps during development.

**Combined step** -- everything in one layer, rebuilt together:

```yaml
steps:
  - run:
      - apt-get update
      - apt-get install -y cuda-toolkit-12-6
      - dpkg -i /tmp/some-package.deb
```

If anything changes, the entire layer rebuilds. Good for related commands that should always run together (like cloning a repo and building it).

**Rule of thumb:** combine commands that are logically one operation (clone + build, download + install). Keep unrelated operations as separate steps for better cache granularity.

### Variable Substitution

You can reference container-magic variables in custom steps:

- `${WORKSPACE}` - Workspace directory path
- `${USER_NAME}` - Non-root user name (if `create: user` was used)
- `${USER_UID}` / `${USER_GID}` - User IDs

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
      - copy: workspace
      - RUN python ${WORKSPACE}/setup.py build
      - RUN ${WORKSPACE}/scripts/init.sh
```

## Default Step Behaviour

If you don't specify `steps`, container-magic applies defaults based on the stage type:

**For stages FROM Docker images** (e.g., `from: python:3.11-slim`):

No default steps.

**For stages FROM other stages** (e.g., `from: base`):

No default steps.

**For the production stage:**

If no steps are specified, `copy: workspace` is added automatically.

## Step Ordering Rules

1. **Steps execute in order** - left to right, top to bottom
2. **User creation before switching** - `create: user` must come before `become: user`
3. **User switching for security** - switch to non-root after setup, use `become: root` if needed for privileged ops

**Common approach:**

```yaml
steps:
  - create: user
  - become: user
  - copy: workspace
```

## Package Installation

Package managers can be used as structured steps. The command name determines which package manager is used:

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

### Registry Defaults

Container-magic applies container-optimised defaults to each package manager automatically. You don't need to add these flags yourself -- they're handled for you:

| Command | Setup | Flags | Cleanup |
|---------|-------|-------|---------|
| `apt-get install` | `apt-get update` | `-y --no-install-recommends` | `rm -rf /var/lib/apt/lists/*` |
| `apk add` | -- | `--no-cache` | -- |
| `dnf install` | -- | `-y` | `dnf clean all` |
| `pip install` | -- | `--no-cache-dir` | -- |

For example, this step:

```yaml
- apt-get:
    install:
      - curl
      - git
```

generates a single `RUN` instruction equivalent to:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends curl git && rm -rf /var/lib/apt/lists/*
```

The defaults are defined in YAML files under `src/container_magic/registry/`. Each file defines the setup, flags, and cleanup for one command:

```
src/container_magic/registry/
  apt-get.yaml
  apk.yaml
  dnf.yaml
  pip.yaml
```

### Per-project Overrides

You can override registry defaults in your `cm.yaml` using the `command_registry` field:

```yaml
command_registry:
  apt-get:
    install:
      flags: "-y"    # Drop --no-install-recommends
      cleanup: ""    # Skip cleanup
```

Overrides replace the entire entry for that command path -- they don't merge with the built-in defaults.

### Adding New Registry Entries

Contributors can add support for new package managers or tools by creating a YAML file in `src/container_magic/registry/`. The file name becomes the command name, and each top-level key is a subcommand:

```yaml
# src/container_magic/registry/pacman.yaml
install:
  setup: "pacman -Sy"
  flags: "--noconfirm --needed"
  cleanup: "pacman -Scc --noconfirm"
```

Each entry supports three optional fields:

- `setup` -- command to run before the main command (e.g. updating the package index)
- `flags` -- flags appended to the command line
- `cleanup` -- command to run after the main command (e.g. clearing caches to reduce layer size)

All three are combined into a single `RUN` instruction to keep the layer count down.

## Common Patterns

### Multi-stage with shared base

```yaml
names:
  project: my-app
  user: nonroot

stages:
  base:
    from: python:3.11-slim
    steps:
      - apt-get:
          install:
            - git
            - build-essential
      - pip:
          install:
            - setuptools
      - create: user
      - become: user

  development:
    from: base

  production:
    from: base
    steps:
      - pip:
          install:
            - gunicorn
      - copy: workspace
```

### Using cached assets for models

```yaml
names:
  project: ml-service
  user: nonroot

assets:
  - model.safetensors: https://huggingface.co/bert-base-uncased/resolve/main/model.safetensors

stages:
  base:
    from: pytorch/pytorch:latest
    steps:
      - pip:
          install:
            - transformers
      - copy: model.safetensors /models/bert.safetensors
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
