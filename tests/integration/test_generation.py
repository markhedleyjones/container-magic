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


def validate_no_consecutive_blank_lines(file_path: Path) -> bool:
    """Validate that file has no more than one consecutive blank line."""
    with open(file_path) as f:
        lines = f.readlines()

    consecutive_blanks = 0
    max_consecutive = 0

    for line in lines:
        if line.strip() == "":
            consecutive_blanks += 1
            max_consecutive = max(max_consecutive, consecutive_blanks)
        else:
            consecutive_blanks = 0

    return max_consecutive <= 1


@pytest.mark.parametrize("name,template", TEST_CASES)
def test_project_generation(name, template, test_output_dir):
    """Test that project generation works and produces valid files."""
    # Create project directory
    project_dir = test_output_dir / name
    project_dir.mkdir(parents=True, exist_ok=True)

    # Run cm init
    result = subprocess.run(
        ["cm", "init", "--here", template],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"cm init failed: {result.stderr}"

    # Check all expected files exist
    expected_files = [
        "Dockerfile",
        "cm.yaml",
        "build.sh",
        "run.sh",
        ".gitignore",
        "workspace",
    ]
    for file in expected_files:
        file_path = project_dir / file
        assert file_path.exists(), f"Missing file: {file}"

    # Justfile should NOT be generated in v3
    assert not (project_dir / "Justfile").exists(), (
        "Justfile should not be generated in v3"
    )

    # Validate files with linters
    assert validate_yaml(project_dir / "cm.yaml"), "YAML validation failed: cm.yaml"
    assert validate_dockerfile(project_dir / "Dockerfile"), (
        "Dockerfile validation failed"
    )
    assert validate_shell_script(project_dir / "build.sh"), "build.sh validation failed"
    assert validate_shell_script(project_dir / "run.sh"), "run.sh validation failed"

    # Validate no excessive blank lines in generated files
    for file_name in ["Dockerfile", "build.sh", "run.sh", "cm.yaml"]:
        file_path = project_dir / file_name
        assert validate_no_consecutive_blank_lines(file_path), (
            f"{file_name} has more than one consecutive blank line"
        )

    # Validate YAML is readable by cm
    result = subprocess.run(
        ["cm", "update"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"cm update failed: {result.stderr}"

    # Check config uses 'from:' not 'frm:'
    config_content = (project_dir / "cm.yaml").read_text()
    assert "frm:" not in config_content, "Config uses 'frm:' instead of 'from:'"

    # Check Dockerfile has required stages
    dockerfile_content = (project_dir / "Dockerfile").read_text()
    assert "FROM" in dockerfile_content and "AS base" in dockerfile_content, (
        "Dockerfile missing base stage"
    )

    # Config should have minimal comments (header only)
    comment_lines = [
        line for line in config_content.split("\n") if line.strip().startswith("#")
    ]
    assert len(comment_lines) == 1, (
        f"Config should only have header link, found {len(comment_lines)}"
    )
    assert "github.com/markhedleyjones/container-magic" in comment_lines[0], (
        "Config missing repository link"
    )
