# Build Steps

The `steps` field in each stage defines how the image is constructed. Container-magic provides built-in steps for common tasks, and supports custom Dockerfile commands for advanced use cases.

## Built-in Steps

### 1. `copy: workspace`

The word `workspace` here is a keyword -- it resolves to the directory named by `names.workspace` (default: `workspace`). This copies the entire workspace directory into the image, typically for production builds. Context-aware -- adds `--chown` when user context is active.

```yaml
stages:
  production:
    from: base
    steps:
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

The keyword form (`copy: workspace`) is the primary mechanism, and literal values are allowed but flagged to catch mistakes.

---

### 2. `copy`

User-context-aware file copy. Behaves like Docker's `COPY` but automatically adds `--chown=<username>:<username>` when user context is active for a non-root user. Lowercase = smart abstraction, uppercase `COPY` = raw Dockerfile passthrough.

```yaml
names:
  image: my-project
  user: nonroot

stages:
  base:
    from: python:3.11-slim
    steps:
      - copy: config.yaml /etc/myservice/config.yaml
      - copy: scripts/init.sh /opt/init.sh
```

**Generated Dockerfile** (with user context active):

```dockerfile
COPY --chown=nonroot:nonroot config.yaml /etc/myservice/config.yaml
COPY --chown=nonroot:nonroot scripts/init.sh /opt/init.sh
```

If the `copy` step appears before user context is active (e.g. after `become: root`), it generates a plain `COPY` without `--chown`. User context is inherited from parent stages -- if a parent ends with user context active, child stages start with it active.

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

When user context is active, `--chown` is added automatically:

```yaml
- copy: --from=builder /usr/local/bin/myapp /usr/local/bin/myapp
```

```dockerfile
COPY --chown=user:user --from=builder /usr/local/bin/myapp /usr/local/bin/myapp
```

The `--from=` argument should reference a stage name defined in the same `cm.yaml`. The stage doesn't need to be a parent -- it can be any stage in the build.

---

### 3. `run`

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

### 4. `env`

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
- `${USER_NAME}` - Non-root user name (set from `names.user`)
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
2. **User context for copies** - `copy` steps automatically add `--chown` when user context is active
3. **Privilege separation** - privileged operations (e.g. `apt-get`) run before user context is activated; use `become: root` to switch back if needed mid-stage

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

Container-magic applies container-optimised defaults to each package manager automatically. You don't need to add these flags yourself -- they're handled for you. The table below is auto-generated from the registry YAML files.

<!-- BEGIN container-magic:registry-defaults -->
| Command | Setup | Flags | Cleanup | Fields |
|---------|-------|-------|---------|--------|
| `apk add` | -- | `--no-cache` | -- | -- |
| `apt-get install` | `apt-get update` | `-y --no-install-recommends` | `rm -rf /var/lib/apt/lists/*` | -- |
| `conda install` | -- | `--yes --quiet --override-channels --channel conda-forge` | -- | `channels (--channel)` |
| `dnf install` | -- | `-y` | `dnf clean all` | -- |
| `mamba install` | -- | `--yes --quiet --override-channels --channel conda-forge` | -- | `channels (--channel)` |
| `micromamba install` | -- | `--yes --quiet --override-channels --channel conda-forge` | -- | `channels (--channel)` |
| `pip install` | -- | `--no-cache-dir` | -- | -- |
<!-- END container-magic:registry-defaults -->

To regenerate this table after editing registry files, run `python -m container_magic.core.registry_docs --update`.

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
  conda.yaml
  mamba.yaml
  micromamba.yaml
```

### Conda, Mamba, Micromamba

Conda-style installers use `conda-forge` by default with `--override-channels` so
any system `.condarc` is ignored. `conda-forge` is a community-maintained channel
that is free to use; Anaconda Inc.'s `defaults` channel requires a paid commercial
license in many cases, so container-magic steers clear of it unless you opt in.

To use a different set of channels, list them on the step:

```yaml
- conda:
    install:
      - pytorch-cuda
      - whisperx
    channels:
      - pytorch
      - nvidia
      - conda-forge
```

The channel order is priority order: the first listed is the highest priority.
The generated command is:

```dockerfile
RUN conda install --yes --quiet --override-channels \
    --channel pytorch --channel nvidia --channel conda-forge \
    pytorch-cuda whisperx
```

`mamba:` and `micromamba:` accept the same `channels:` field with the same
defaults. Pick whichever is installed in your base image - `conda` for the
reference implementation, `mamba` or `micromamba` for faster installs.

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

Each entry supports the following optional fields:

- `setup` -- command to run before the main command (e.g. updating the package index)
- `flags` -- flags appended to the command line
- `cleanup` -- command to run after the main command (e.g. clearing caches to reduce layer size)
- `fields` -- declare step fields that expand to CLI flags (e.g. conda's `channels`)

All are combined into a single `RUN` instruction to keep the layer count down.

#### Step fields that expand to flags

When a tool accepts a flag that is repeated in priority order (like conda's
`--channel`), the registry can declare a `fields` block so users list values
naturally in their step rather than memorising a flag string:

```yaml
# src/container_magic/registry/conda.yaml
install:
  flags: "--yes --quiet --override-channels"
  fields:
    channels:
      flag: "--channel"
      default:
        - conda-forge
```

A user step like `conda: {install: [pkg], channels: [a, b]}` expands to
`conda install --yes --quiet --override-channels --channel a --channel b pkg`.
If the user omits `channels:`, the `default` list is used.

Each field spec takes:

- `flag` -- the CLI flag name (e.g. `--channel`)
- `default` -- a list of values applied when the user doesn't specify the field
- `type` -- how to expand the values. Currently only `repeated_flag` (default)
  is supported: one `<flag> <value>` pair per item in order.

Field names on user steps that aren't declared in the registry are rejected
with a clear error message listing the valid fields.

## Common Patterns

### Multi-stage with shared base

```yaml
names:
  image: my-app
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
  image: ml-service
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

## Advanced: User Management Steps

When `names.user` is set to anything other than `root`, container-magic automatically creates that user and switches to it in leaf stages. These explicit steps are optional -- they exist for cases where the implicit behaviour isn't enough.

### `create: user`

Explicitly creates the user defined by `names.user` with uid/gid 1000. Useful when you need to control where in the build the user is created, or when you are copying files that must be owned by that user before the end of the stage.

```yaml
steps:
  - create: user  # creates names.user with uid=1000, gid=1000
```

The word `user` is a keyword that resolves to the value of `names.user`. It cannot be used when `names.user` is `root`.

**Defaults:**

- `uid`: 1000
- `gid`: 1000
- `home`: `/home/<username>`

For rare cases where the host uid/gid must differ, `build.sh` accepts `--uid` and `--gid` flags.

**`create: <literal>`** creates a user with that exact name. Use this for secondary users such as service accounts:

```yaml
steps:
  - create: www-data-custom
```

**`create: root`** is always an error. Root exists in every container image by default.

When any stage contains an explicit `create: user`, implicit user creation is disabled globally -- you take full control of where and when the user is created.

---

### `become: <target>`

Switches the active user context. Sets the Dockerfile `USER` directive and controls whether subsequent `copy` steps add `--chown`.

**`become: user`** (keyword) - switches to the user defined by `names.user`. Cannot be used when `names.user` is `root`.

**`become: root`** - switches back to root. Useful for privileged operations after switching to the non-root user.

**`become: <literal>`** - switches to any other user by name (e.g. `become: www-data`). Docker resolves the name against `/etc/passwd` at build time, so this works for users that already exist in the base image without a `create` step.

**Generated Dockerfile:** `USER <username>`

**Example -- explicit ownership control:**

```yaml
names:
  image: my-project
  user: nonroot

stages:
  base:
    from: python:3.11-slim
    steps:
      - create: user
      - become: user                    # USER nonroot
      - copy: entrypoint.sh /opt/       # COPY --chown=nonroot:nonroot ...
      - become: root                    # USER root
      - copy: default.conf /etc/nginx/  # COPY default.conf /etc/nginx/ (no --chown)
```
