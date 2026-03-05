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
        "Justfile",
        "cm.yaml",
        "build.sh",
        "run.sh",
        ".gitignore",
        "workspace",
    ]
    for file in expected_files:
        file_path = project_dir / file
        assert file_path.exists(), f"Missing file: {file}"

    # Validate files with linters
    assert validate_yaml(project_dir / "cm.yaml"), "YAML validation failed: cm.yaml"
    assert validate_dockerfile(project_dir / "Dockerfile"), (
        "Dockerfile validation failed"
    )
    assert validate_shell_script(project_dir / "build.sh"), "build.sh validation failed"
    assert validate_shell_script(project_dir / "run.sh"), "run.sh validation failed"
    assert validate_justfile(project_dir / "Justfile"), "Justfile validation failed"

    # Validate no excessive blank lines in generated files
    for file_name in ["Dockerfile", "Justfile", "build.sh", "run.sh", "cm.yaml"]:
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

    # Check Justfile has required targets
    justfile_content = (project_dir / "Justfile").read_text()
    assert "build" in justfile_content, "Justfile missing build target"

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


def test_justfile_run_command_order(test_output_dir):
    """Test that Justfile run recipe has correct command structure.

    Validates that container flags (like --interactive, --tty) are added
    to RUN_ARGS before the image name, not after. This is critical because
    docker/podman require: `run [flags] IMAGE [command]`
    """
    # Use an existing generated project or create one
    project_dir = test_output_dir / "python"
    if not project_dir.exists():
        project_dir.mkdir(parents=True)
        result = subprocess.run(
            ["cm", "init", "--here", "python"],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"cm init failed: {result.stderr}"

    justfile_content = (project_dir / "Justfile").read_text()

    # Find positions of key patterns in the Justfile
    image_pattern = 'RUN_ARGS+=("${IMAGE}")'
    tty_pattern = 'RUN_ARGS+=("--interactive"'

    # Use rfind for IMAGE to match the foreground (non-detach) path —
    # the detach path intentionally omits TTY flags.
    image_pos = justfile_content.rfind(image_pattern)
    tty_pos = justfile_content.find(tty_pattern)

    assert image_pos >= 0, f"Could not find '{image_pattern}' in Justfile"
    assert tty_pos >= 0, f"Could not find '{tty_pattern}' in Justfile"

    # TTY flags must come before the image in the foreground path
    assert tty_pos < image_pos, (
        "TTY flags (--interactive, --tty) must be added to RUN_ARGS BEFORE the image. "
        f"Found --interactive at position {tty_pos}, IMAGE at position {image_pos}. "
        "Container runtimes require: `run [flags] IMAGE [command]`"
    )


def test_linter_availability():
    """Display which linters are available (informational)."""
    print("\n=== Available Linters ===")
    for name, path in LINTERS.items():
        status = "✓" if path else "✗"
        print(f"{status} {name}: {path or 'not found'}")
