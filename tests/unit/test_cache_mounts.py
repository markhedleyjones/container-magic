"""Tests for opt-in BuildKit cache mounts on package-manager steps."""

from tests.unit.conftest import generate_dockerfile_from_dict as _generate


def _config(steps, **extra):
    return {
        "names": {"image": "test", "user": "root"},
        "stages": {
            "base": {"from": "debian:bookworm-slim", "steps": steps},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
        **extra,
    }


def test_no_cache_mount_by_default():
    content = _generate(_config([{"apt-get": {"install": ["curl"]}}]))
    assert "--mount=type=cache" not in content
    # The normal cleanup is retained when caching is off.
    assert "rm -rf /var/lib/apt/lists/*" in content


def test_apt_cache_mount_when_enabled():
    content = _generate(
        _config([{"apt-get": {"install": ["curl", "git"]}}], cache_mounts=True)
    )
    assert "--mount=type=cache,target=/var/cache/apt,sharing=locked" in content
    assert "--mount=type=cache,target=/var/lib/apt,sharing=locked" in content
    # docker-clean is removed so downloaded debs persist in the cache mount.
    assert "rm -f /etc/apt/apt.conf.d/docker-clean" in content
    # the apt-list cleanup is dropped (the lists live in the cache mount now).
    assert "rm -rf /var/lib/apt/lists/*" not in content


def test_apt_cache_mount_is_a_single_run_with_mounts_first():
    content = _generate(
        _config([{"apt-get": {"install": ["curl"]}}], cache_mounts=True)
    )
    run_lines = [
        line
        for line in content.splitlines()
        if line.lstrip().startswith("RUN --mount=type=cache,target=/var/cache/apt")
    ]
    assert len(run_lines) == 1
    # install is still chained into the same RUN
    assert "apt-get update" in content
    assert "apt-get install -y --no-install-recommends curl" in content


def test_pip_unaffected_by_cache_mounts():
    # pip has no cache config yet, so enabling cache_mounts leaves it unchanged.
    content = _generate(_config([{"pip": {"install": ["numpy"]}}], cache_mounts=True))
    assert "--mount=type=cache" not in content
    assert "--no-cache-dir" in content
