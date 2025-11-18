"""Tests for container runtime detection."""

import pytest

from container_magic.core.runtime import Runtime, detect_runtime, get_runtime


def test_detect_runtime():
    """Test that runtime detection returns a valid runtime or None."""
    runtime = detect_runtime()
    assert runtime in [Runtime.DOCKER, Runtime.PODMAN, None]


def test_get_runtime_auto():
    """Test auto runtime selection."""
    try:
        runtime = get_runtime("auto")
        assert runtime in [Runtime.DOCKER, Runtime.PODMAN]
    except RuntimeError as e:
        # If neither is installed, should raise RuntimeError
        assert "Neither Docker nor Podman found" in str(e)


def test_get_runtime_invalid():
    """Test that invalid runtime backend raises ValueError."""
    with pytest.raises(ValueError, match="Invalid runtime backend"):
        get_runtime("invalid")
