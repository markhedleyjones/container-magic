"""Generate documentation from registry YAML files.

Keeps the Registry Defaults table in docs/build-steps.md in sync with
src/container_magic/registry/*.yaml so new tools don't need a second
manual documentation step.
"""

from pathlib import Path

import yaml

_REGISTRY_DIR = Path(__file__).parent.parent / "registry"
_DOCS_BEGIN = "<!-- BEGIN container-magic:registry-defaults -->"
_DOCS_END = "<!-- END container-magic:registry-defaults -->"


def _cell(value: str) -> str:
    """Format a value for a markdown table cell."""
    if not value:
        return "--"
    return f"`{value}`"


def _fields_summary(fields_data: dict) -> str:
    """Summarise a 'fields' block for the table (e.g. 'channels (--channel)')."""
    if not isinstance(fields_data, dict):
        return ""
    parts = []
    for name, spec in fields_data.items():
        if not isinstance(spec, dict):
            continue
        flag = spec.get("flag", "")
        if flag:
            parts.append(f"{name} ({flag})")
        else:
            parts.append(name)
    return ", ".join(parts)


def _expanded_flags(entry: dict) -> str:
    """Expand field defaults into the flags string for display."""
    flags = entry.get("flags", "")
    fields = entry.get("fields")
    if not isinstance(fields, dict):
        return flags
    extras = []
    for spec in fields.values():
        if not isinstance(spec, dict):
            continue
        flag = spec.get("flag", "")
        default = spec.get("default") or []
        if not flag or not default:
            continue
        for value in default:
            extras.append(f"{flag} {value}")
    if not extras:
        return flags
    extras_str = " ".join(extras)
    return f"{flags} {extras_str}".strip()


def generate_registry_table() -> str:
    """Return the markdown table of registry defaults.

    One row per subcommand across all registry YAML files, sorted by command
    name. The 'Flags' column includes any expanded defaults from declared
    fields so the table reflects the actual command shape.
    """
    rows = []
    for yaml_file in sorted(_REGISTRY_DIR.glob("*.yaml")):
        tool_name = yaml_file.stem
        with yaml_file.open() as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            continue
        for subcommand, entry in data.items():
            if not isinstance(entry, dict):
                continue
            command = f"{tool_name} {subcommand}"
            setup = entry.get("setup", "")
            flags = _expanded_flags(entry)
            cleanup = entry.get("cleanup", "")
            fields = _fields_summary(entry.get("fields", {}))
            rows.append((command, setup, flags, cleanup, fields))

    rows.sort(key=lambda r: r[0])

    lines = [
        "| Command | Setup | Flags | Cleanup | Fields |",
        "|---------|-------|-------|---------|--------|",
    ]
    for command, setup, flags, cleanup, fields in rows:
        lines.append(
            f"| `{command}` | {_cell(setup)} | {_cell(flags)} | "
            f"{_cell(cleanup)} | {_cell(fields)} |"
        )
    return "\n".join(lines)


def generate_managed_block() -> str:
    """Return the full managed block (markers + content) for insertion."""
    table = generate_registry_table()
    return f"{_DOCS_BEGIN}\n{table}\n{_DOCS_END}"


def extract_managed_block(content: str) -> str:
    """Return the managed block currently in a document, or raise if missing."""
    begin_idx = content.find(_DOCS_BEGIN)
    end_idx = content.find(
        _DOCS_END, begin_idx + len(_DOCS_BEGIN) if begin_idx >= 0 else 0
    )
    if begin_idx < 0 or end_idx < 0:
        raise ValueError(
            f"Managed block markers not found. Expected '{_DOCS_BEGIN}' and "
            f"'{_DOCS_END}' in the document."
        )
    return content[begin_idx : end_idx + len(_DOCS_END)]


def update_docs_file(docs_path: Path) -> bool:
    """Rewrite the managed block in a docs file. Returns True if changes were made."""
    content = docs_path.read_text()
    current = extract_managed_block(content)
    desired = generate_managed_block()
    if current == desired:
        return False
    updated = content.replace(current, desired)
    docs_path.write_text(updated)
    return True


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--update",
        action="store_true",
        help="Rewrite the managed block in place. Default is to print to stdout.",
    )
    parser.add_argument(
        "--docs-path",
        type=Path,
        default=_project_root() / "docs" / "build-steps.md",
        help="Path to the documentation file containing the managed block.",
    )
    args = parser.parse_args()

    if args.update:
        changed = update_docs_file(args.docs_path)
        if changed:
            print(f"Updated {args.docs_path}")
        else:
            print(f"{args.docs_path} already up to date")
        return 0

    print(generate_managed_block())
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
