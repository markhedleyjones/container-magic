"""Tests for optional base-image digest pinning."""

import container_magic.generators.dockerfile as dockerfile_mod
from container_magic.core import digest as digest_mod
from tests.unit.conftest import generate_dockerfile_from_dict as _generate


def _config(**extra):
    return {
        "names": {"image": "test", "user": "app"},
        "stages": {
            "base": {"from": "debian:bookworm-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
        **extra,
    }


def test_not_pinned_by_default(monkeypatch):
    monkeypatch.setattr(dockerfile_mod, "resolve_image_digest", lambda ref: "sha256:x")
    content = _generate(_config())
    assert "FROM debian:bookworm-slim AS base" in content
    assert "@sha256" not in content


def test_resolver_not_called_when_disabled(monkeypatch):
    calls = []
    monkeypatch.setattr(
        dockerfile_mod,
        "resolve_image_digest",
        lambda ref: calls.append(ref) or "sha256:x",
    )
    _generate(_config())
    assert calls == []


def test_pinned_when_enabled(monkeypatch):
    monkeypatch.setattr(
        dockerfile_mod, "resolve_image_digest", lambda ref: "sha256:deadbeef"
    )
    content = _generate(_config(pin_base_images=True))
    assert "FROM debian:bookworm-slim@sha256:deadbeef AS base" in content


def test_stage_references_not_pinned(monkeypatch):
    monkeypatch.setattr(
        dockerfile_mod, "resolve_image_digest", lambda ref: "sha256:deadbeef"
    )
    content = _generate(_config(pin_base_images=True))
    # development/production build FROM the 'base' stage, not an external image.
    assert "FROM base AS development" in content
    assert "FROM base AS production" in content


def test_unresolvable_falls_back_to_tag(monkeypatch, capsys):
    monkeypatch.setattr(dockerfile_mod, "resolve_image_digest", lambda ref: None)
    content = _generate(_config(pin_base_images=True))
    assert "FROM debian:bookworm-slim AS base" in content
    assert "@sha256" not in content
    assert "could not resolve a digest" in capsys.readouterr().err


# --- resolver unit tests (no network) ---


def test_run_returns_digest_on_clean_output():
    assert digest_mod._run(["echo", "sha256:abc123"]) == "sha256:abc123"


def test_run_rejects_non_digest_output():
    assert digest_mod._run(["echo", "not-a-digest"]) is None


def test_run_returns_none_on_failure():
    assert digest_mod._run(["false"]) is None


def test_resolve_returns_none_when_no_tools(monkeypatch):
    monkeypatch.setattr(digest_mod.shutil, "which", lambda name: None)
    assert digest_mod.resolve_image_digest("debian:bookworm-slim") is None
