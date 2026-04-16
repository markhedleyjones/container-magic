"""Tests for registry documentation generation."""

from pathlib import Path

import pytest

from container_magic.core.registry_docs import (
    extract_managed_block,
    generate_managed_block,
    generate_registry_table,
    update_docs_file,
)


_DOCS_PATH = Path(__file__).resolve().parents[2] / "docs" / "build-steps.md"


def test_managed_block_matches_registry_state():
    """The managed block in docs/build-steps.md must match generated content.

    If this fails, run `python -m container_magic.core.registry_docs --update`
    to regenerate the table from current registry YAML files.
    """
    content = _DOCS_PATH.read_text()
    current = extract_managed_block(content)
    desired = generate_managed_block()
    assert current == desired, (
        "Registry docs table is out of sync with registry YAML files. "
        "Run: python -m container_magic.core.registry_docs --update"
    )


def test_table_includes_known_tools():
    """The generated table must include all built-in tools."""
    table = generate_registry_table()
    for tool in (
        "apt-get install",
        "apk add",
        "dnf install",
        "pip install",
        "conda install",
        "mamba install",
        "micromamba install",
    ):
        assert f"`{tool}`" in table, f"Missing {tool} in generated table"


def test_fields_are_rendered(tmp_path):
    """Registry entries with fields show them in the Fields column."""
    table = generate_registry_table()
    # conda/mamba/micromamba all declare a channels field
    assert "channels (--channel)" in table


def test_flags_include_expanded_field_defaults():
    """The Flags column shows the default channels inline so readers see the actual command."""
    table = generate_registry_table()
    assert "--channel conda-forge" in table


def test_extract_raises_if_markers_missing():
    with pytest.raises(ValueError, match="markers not found"):
        extract_managed_block("no markers here")


def test_update_roundtrip(tmp_path):
    """A file with current content is not rewritten; drifted content is updated."""
    fake_docs = tmp_path / "doc.md"
    fake_docs.write_text(f"preamble\n\n{generate_managed_block()}\n\nafter\n")

    # No drift - no change
    assert update_docs_file(fake_docs) is False

    # Simulate drift
    fake_docs.write_text(
        "preamble\n\n"
        "<!-- BEGIN container-magic:registry-defaults -->\n"
        "stale content\n"
        "<!-- END container-magic:registry-defaults -->\n"
        "\nafter\n"
    )
    assert update_docs_file(fake_docs) is True
    # Block is now up to date
    assert update_docs_file(fake_docs) is False
    # Surrounding content preserved
    updated = fake_docs.read_text()
    assert updated.startswith("preamble\n\n")
    assert updated.endswith("\nafter\n")
