# Troubleshooting

## Python pip on Debian/Ubuntu (PEP 668)

Modern versions of Debian (12+) and Ubuntu (24.04+) enforce [PEP 668](https://peps.python.org/pep-0668/), which prevents pip from installing packages system-wide. If you try to use pip on these distributions, you'll encounter an error.

**Solution — use one of these approaches:**

=== "Python official image"

    ```yaml
    stages:
      base:
        from: python:3.11-slim
        packages:
          pip:
            - requests
            - numpy
    ```

=== "Install python3-full"

    ```yaml
    stages:
      base:
        from: ubuntu:24.04
        packages:
          apt:
            - python3-full
          pip:
            - requests
    ```

=== "--break-system-packages"

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
          - RUN pip install --break-system-packages requests
    ```

    !!! warning
        Only use `--break-system-packages` if you understand the security implications.

## "Error: uses 'create_user' or 'become_user' but production.user is not defined"

Add a `user` section with a `production` entry to your config:

```yaml
user:
  production:
    name: appuser
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

Use `cached_assets` to download once and reuse:

```yaml
cached_assets:
  - url: https://large-file.example.com/model.tar.gz
    dest: /models/model.tar.gz
steps:
  - copy_cached_assets
```

See [Cached Assets](cached-assets.md) for full details.

## Permission Denied When Running as Non-root

Use lowercase `copy` instead of uppercase `COPY` — it automatically sets ownership via `--chown` when `become_user` is active:

```yaml
steps:
  - create_user
  - become_user
  - copy app /app
```

See [User Handling](user-handling.md) for more on copy ownership.
