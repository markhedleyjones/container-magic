"""Shared test helpers for unit tests."""

from pathlib import Path
from tempfile import TemporaryDirectory

from container_magic.core.config import ContainerMagicConfig
from container_magic.generators.dockerfile import generate_dockerfile


def generate_dockerfile_from_dict(config_dict):
    """Generate a Dockerfile from a config dict and return its content."""
    config = ContainerMagicConfig(**config_dict)
    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        generate_dockerfile(config, output_path)
        return output_path.read_text()


def get_stage_block(content, stage_name):
    """Extract lines for a single stage from a generated Dockerfile."""
    lines = content.splitlines()
    start = None
    end = None
    for i, line in enumerate(lines):
        if "FROM " in line and line.rstrip().endswith(f" AS {stage_name}"):
            start = i
        elif start is not None and line.startswith("FROM "):
            end = i
            break
    if start is not None:
        block_lines = lines[start : end if end else len(lines)]
        while block_lines and (
            block_lines[-1].startswith("#") or not block_lines[-1].strip()
        ):
            block_lines.pop()
        return "\n".join(block_lines)
    return ""
