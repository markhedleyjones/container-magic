# Troubleshooting

## Upgrading from v2

### `run` and `build` commands not found

In v2, container-magic installed generic `run` and `build` commands alongside `cm`. These have been removed in v3 because the names are too generic and clash with other tools.

**Replace with:**

| v2 | v3 |
|----|-----|
| `build` | `cm build` |
| `run <command>` | `cm run <command>` |
| `just stop` | `cm stop` |
| `just clean` | `cm clean` |

### Justfile no longer generated

v3 replaces the Justfile with Python-native `cm build` and `cm run` commands. If you have a leftover `Justfile`, you can safely delete it. Running `cm update` will warn about it.

### Standalone command scripts removed

Per-command scripts (e.g. `train.sh`) are no longer generated. Custom commands are now invoked through `cm run <command>` or `./run.sh <command>`.

## Python pip on Debian/Ubuntu (PEP 668)

Modern versions of Debian (12+) and Ubuntu (24.04+) enforce [PEP 668](https://peps.python.org/pep-0668/), which prevents pip from installing packages system-wide. If you try to use pip on these distributions, you'll encounter an error.

**Solution -- use one of these approaches:**

=== "Python official image"

    ```yaml
    stages:
      base:
        from: python:3.11-slim
        steps:
          - pip:
              install:
                - requests
                - numpy
    ```

=== "Install python3-full"

    ```yaml
    stages:
      base:
        from: ubuntu:24.04
        steps:
          - apt-get:
              install:
                - python3-full
          - pip:
              install:
                - requests
    ```

=== "--break-system-packages"

    ```yaml
    stages:
      base:
        from: ubuntu:24.04
        steps:
          - apt-get:
              install:
                - python3
                - python3-pip
          - RUN pip install --break-system-packages requests
    ```

    !!! warning
        Only use `--break-system-packages` if you understand the security implications.

## Missing `names.user`

The `names.user` field is required. If it is missing, you will get a validation error. Add it to your config:

```yaml
names:
  image: my-project
  user: nonroot           # or 'root' if no custom user is needed
```

If you set `user` to anything other than `root`, add `create: user` and `become: user` steps to your base stage:

```yaml
stages:
  base:
    from: python:3.11-slim
    steps:
      - create: user
      - become: user
```

## Custom Step Not Producing Expected Output

Steps that don't match a built-in keyword or Dockerfile instruction are automatically wrapped with `RUN`. Both of these are equivalent:

```yaml
steps:
  - RUN apt-get install -y something     # explicit RUN
  - apt-get install -y something         # RUN is prepended automatically
```

For other Dockerfile instructions (`ENV`, `COPY`, `WORKDIR`, etc.), use the uppercase keyword explicitly.

## Build Takes Too Long When Downloading Assets

Use `assets` to download once and cache locally:

```yaml
names:
  image: my-project
  user: root

assets:
  - model.tar.gz: https://large-file.example.com/model.tar.gz

stages:
  base:
    from: python:3-slim
    steps:
      - copy: model.tar.gz /models/model.tar.gz
```

See [Cached Assets](cached-assets.md) for full details.

## Permission Denied When Running as Non-root

Use lowercase `copy` instead of uppercase `COPY` - it automatically sets ownership via `--chown` when `become` is active:

```yaml
steps:
  - create: user
  - become: user
  - copy: config.yaml /etc/myservice/config.yaml
```

See [User Handling](user-handling.md) for more on copy ownership.
