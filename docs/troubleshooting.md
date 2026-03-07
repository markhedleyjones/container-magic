# Troubleshooting

## Python pip on Debian/Ubuntu (PEP 668)

Modern versions of Debian (12+) and Ubuntu (24.04+) enforce [PEP 668](https://peps.python.org/pep-0668/), which prevents pip from installing packages system-wide. If you try to use pip on these distributions, you'll encounter an error.

**Solution -- use one of these approaches:**

=== "Python official image"

    ```yaml
    stages:
      base:
        from: python:3.11-slim
        steps:
          - pip: {install: [requests, numpy]}
    ```

=== "Install python3-full"

    ```yaml
    stages:
      base:
        from: ubuntu:24.04
        steps:
          - apt-get: {install: [python3-full]}
          - pip: {install: [requests]}
    ```

=== "--break-system-packages"

    ```yaml
    stages:
      base:
        from: ubuntu:24.04
        steps:
          - apt-get: {install: [python3, python3-pip]}
          - RUN pip install --break-system-packages requests
    ```

    !!! warning
        Only use `--break-system-packages` if you understand the security implications.

## "Error: no user is configured"

Add a `create_user` step to your build stages:

```yaml
stages:
  base:
    from: python:3.11-slim
    steps:
      - create_user: appuser
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

Use `project.assets` to download once and cache locally:

```yaml
project:
  name: my-project
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
  - create_user: appuser
  - become: appuser
  - copy app /app
```

See [User Handling](user-handling.md) for more on copy ownership.
