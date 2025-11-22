"""Integration tests for project generation and validation."""

import shutil
import subprocess
from pathlib import Path

import pytest

# Test cases: (name, template)
TEST_CASES = [
    ("python", "python"),
    ("python-3-11", "python:3.11"),
    ("ubuntu", "ubuntu"),
    ("ubuntu-22-04", "ubuntu:22.04"),
    ("debian", "debian"),
    ("alpine", "alpine"),
    ("pytorch", "pytorch/pytorch"),
    ("pytorch-cuda", "pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime"),
    ("nvidia-cuda", "nvidia/cuda:12.4.0-runtime-ubuntu22.04"),
]

# Linting tools (optional)
LINTERS = {
    "yamlfmt": shutil.which("yamlfmt"),
    "hadolint": shutil.which("hadolint"),
    "shellcheck": shutil.which("shellcheck"),
    "just": shutil.which("just"),
}


@pytest.fixture(scope="session")
def test_output_dir():
    """Create directory for test projects in repo for manual inspection."""
    import os

    repo_root = Path(os.getcwd())
    output_dir = repo_root / "test-generated-projects"
    output_dir.mkdir(exist_ok=True)
    return output_dir


def validate_yaml(yaml_file: Path) -> bool:
    """Validate YAML file with yamlfmt."""
    if not LINTERS["yamlfmt"]:
        return True
    result = subprocess.run(
        [
            "yamlfmt",
            "-formatter",
            "retain_line_breaks=true",
            "-lint",
            str(yaml_file),
        ],
        capture_output=True,
    )
    return result.returncode == 0


def validate_dockerfile(dockerfile: Path) -> bool:
    """Validate Dockerfile with hadolint (errors only)."""
    if not LINTERS["hadolint"]:
        return True
    result = subprocess.run(
        ["hadolint", "--failure-threshold", "error", str(dockerfile)],
        capture_output=True,
    )
    return result.returncode == 0


def validate_shell_script(script: Path) -> bool:
    """Validate shell script with shellcheck."""
    if not LINTERS["shellcheck"]:
        return True
    result = subprocess.run(
        ["shellcheck", str(script)],
        capture_output=True,
    )
    return result.returncode == 0


def validate_justfile(justfile: Path) -> bool:
    """Validate Justfile syntax."""
    if not LINTERS["just"]:
        return True
    result = subprocess.run(
        ["just", "--justfile", str(justfile), "--summary"],
        capture_output=True,
    )
    return result.returncode == 0


@pytest.mark.parametrize("name,template", TEST_CASES)
@pytest.mark.parametrize("compact", [False, True], ids=["full", "compact"])
def test_project_generation(name, template, compact, test_output_dir):
    """Test that project generation works and produces valid files."""
    # Determine variant name and config file
    variant_name = f"{name}-compact" if compact else name
    config_file = "cm.yaml" if compact else "container-magic.yaml"
    compact_flag = ["--compact"] if compact else []

    # Create project directory
    project_dir = test_output_dir / variant_name
    project_dir.mkdir(parents=True, exist_ok=True)

    # Run cm init
    result = subprocess.run(
        ["cm", "init", "--here", *compact_flag, template],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"cm init failed: {result.stderr}"

    # Check all expected files exist
    expected_files = [
        "Dockerfile",
        "Justfile",
        config_file,
        "build.sh",
        "run.sh",
        ".gitignore",
        "workspace",
    ]
    for file in expected_files:
        file_path = project_dir / file
        assert file_path.exists(), f"Missing file: {file}"

    # Validate files with linters
    assert validate_yaml(project_dir / config_file), (
        f"YAML validation failed: {config_file}"
    )
    assert validate_dockerfile(project_dir / "Dockerfile"), (
        "Dockerfile validation failed"
    )
    assert validate_shell_script(project_dir / "build.sh"), "build.sh validation failed"
    assert validate_shell_script(project_dir / "run.sh"), "run.sh validation failed"
    assert validate_justfile(project_dir / "Justfile"), "Justfile validation failed"

    # Validate YAML is readable by cm
    result = subprocess.run(
        ["cm", "update"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"cm update failed: {result.stderr}"

    # Check config uses 'from:' not 'frm:'
    config_content = (project_dir / config_file).read_text()
    assert "frm:" not in config_content, "Config uses 'frm:' instead of 'from:'"

    # Check Dockerfile has required stages
    dockerfile_content = (project_dir / "Dockerfile").read_text()
    assert "FROM" in dockerfile_content and "AS base" in dockerfile_content, (
        "Dockerfile missing base stage"
    )

    # Check Justfile has required targets
    justfile_content = (project_dir / "Justfile").read_text()
    assert "build" in justfile_content, "Justfile missing build target"

    # Compact should have no comments, full should have comments
    if compact:
        assert not any(
            line.startswith("#") for line in config_content.split("\n") if line.strip()
        ), "Compact config contains comments"
    else:
        assert "# Project configuration" in config_content, (
            "Full config missing comments"
        )


def test_linter_availability():
    """Display which linters are available (informational)."""
    print("\n=== Available Linters ===")
    for name, path in LINTERS.items():
        status = "✓" if path else "✗"
        print(f"{status} {name}: {path or 'not found'}")
