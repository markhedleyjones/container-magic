"""Tests for .dockerignore managed section."""

from container_magic.cli.main import (
    _DOCKERIGNORE_BEGIN,
    _DOCKERIGNORE_END,
    update_dockerignore,
)


def test_creates_file_when_missing(tmp_path):
    """Create .dockerignore with managed section if no file exists."""
    update_dockerignore(tmp_path, "workspace")
    content = (tmp_path / ".dockerignore").read_text()
    assert content.startswith(_DOCKERIGNORE_BEGIN)
    assert "!workspace/" in content
    assert "!workspace/**" in content
    assert "!.cm-cache/" in content
    assert "*\n" in content


def test_prepends_to_existing_file(tmp_path):
    """Prepend managed section to existing .dockerignore without markers."""
    (tmp_path / ".dockerignore").write_text("node_modules/\n.env\n")
    update_dockerignore(tmp_path, "workspace")
    content = (tmp_path / ".dockerignore").read_text()
    lines = content.split("\n")
    assert lines[0] == _DOCKERIGNORE_BEGIN
    assert "node_modules/" in lines
    assert ".env" in lines


def test_replaces_managed_section(tmp_path):
    """Replace existing managed section on workspace name change."""
    initial = "\n".join(
        [
            _DOCKERIGNORE_BEGIN,
            "*",
            "!old-workspace/",
            "!old-workspace/**",
            "!.cm-cache/",
            "!.cm-cache/**",
            _DOCKERIGNORE_END,
            "",
            "!extra-file",
            "",
        ]
    )
    (tmp_path / ".dockerignore").write_text(initial)
    update_dockerignore(tmp_path, "src")
    content = (tmp_path / ".dockerignore").read_text()
    assert "!src/" in content
    assert "!src/**" in content
    assert "!old-workspace/" not in content
    assert "!extra-file" in content


def test_preserves_user_additions_below(tmp_path):
    """User additions below the managed section survive an update."""
    initial = "\n".join(
        [
            _DOCKERIGNORE_BEGIN,
            "*",
            "!workspace/",
            "!workspace/**",
            "!.cm-cache/",
            "!.cm-cache/**",
            _DOCKERIGNORE_END,
            "",
            "# My custom additions",
            "!config.yaml",
            "",
        ]
    )
    (tmp_path / ".dockerignore").write_text(initial)
    update_dockerignore(tmp_path, "workspace")
    content = (tmp_path / ".dockerignore").read_text()
    assert "# My custom additions" in content
    assert "!config.yaml" in content


def test_preserves_user_additions_above(tmp_path):
    """User additions above the managed section survive an update."""
    initial = "\n".join(
        [
            "# Project-specific ignores",
            "",
            _DOCKERIGNORE_BEGIN,
            "*",
            "!workspace/",
            "!workspace/**",
            "!.cm-cache/",
            "!.cm-cache/**",
            _DOCKERIGNORE_END,
            "",
        ]
    )
    (tmp_path / ".dockerignore").write_text(initial)
    update_dockerignore(tmp_path, "workspace")
    content = (tmp_path / ".dockerignore").read_text()
    assert "# Project-specific ignores" in content


def test_trailing_newline(tmp_path):
    """Output always ends with a newline."""
    update_dockerignore(tmp_path, "workspace")
    content = (tmp_path / ".dockerignore").read_text()
    assert content.endswith("\n")


def test_custom_workspace_name(tmp_path):
    """Workspace name is reflected in the allowlist."""
    update_dockerignore(tmp_path, "my-code")
    content = (tmp_path / ".dockerignore").read_text()
    assert "!my-code/" in content
    assert "!my-code/**" in content
    assert "!workspace/" not in content
