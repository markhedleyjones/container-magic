from typing import List
"""Reusable validation utilities for linting and formatting checks.

Provides consistent validation across tests and generators.
"""

import shutil
import subprocess
from pathlib import Path


class ValidationResult:
    """Result of a validation check."""

    def __init__(self, passed: bool, message: str = ""):
        self.passed = passed
        self.message = message

    def __bool__(self):
        return self.passed

    def __str__(self):
        return self.message if self.message else ("PASS" if self.passed else "FAIL")


def validate_no_consecutive_blank_lines(
    file_path: Path, max_consecutive: int = 1
) -> ValidationResult:
    """
    Validate that file has no more than max_consecutive blank lines.

    Args:
        file_path: Path to file to check
        max_consecutive: Maximum allowed consecutive blank lines (default 1)

    Returns:
        ValidationResult indicating success/failure
    """
    try:
        with open(file_path) as f:
            lines = f.readlines()
    except Exception as e:
        return ValidationResult(False, f"Failed to read file: {e}")

    consecutive_blanks = 0
    found_excessive = []

    for i, line in enumerate(lines, start=1):
        if line.strip() == "":
            consecutive_blanks += 1
            if consecutive_blanks > max_consecutive:
                found_excessive.append(i)
        else:
            consecutive_blanks = 0

    if found_excessive:
        lines_str = ", ".join(str(line) for line in found_excessive[:5])
        if len(found_excessive) > 5:
            lines_str += f" (and {len(found_excessive) - 5} more)"
        return ValidationResult(
            False,
            f"Found {len(found_excessive)} lines with excessive blank lines at: {lines_str}",
        )

    return ValidationResult(True)


def validate_yaml(yaml_file: Path) -> ValidationResult:
    """Validate YAML file with yamlfmt."""
    yamlfmt = shutil.which("yamlfmt")
    if not yamlfmt:
        return ValidationResult(True, "yamlfmt not available (skipped)")

    result = subprocess.run(
        [
            "yamlfmt",
            "-formatter",
            "retain_line_breaks=true",
            "-lint",
            str(yaml_file),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return ValidationResult(False, f"yamlfmt failed:\n{result.stderr}")

    return ValidationResult(True, "yamlfmt: OK")


def validate_dockerfile(dockerfile: Path) -> ValidationResult:
    """Validate Dockerfile with hadolint (errors only)."""
    hadolint = shutil.which("hadolint")
    if not hadolint:
        return ValidationResult(True, "hadolint not available (skipped)")

    result = subprocess.run(
        ["hadolint", "--failure-threshold", "error", str(dockerfile)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return ValidationResult(
            False, f"hadolint failed:\n{result.stderr}\n{result.stdout}"
        )

    return ValidationResult(True, "hadolint: OK")


def validate_shell_script(
    script: Path, check_formatting: bool = True
) -> ValidationResult:
    """Validate shell script with shellcheck and optionally shfmt."""
    messages = []
    all_passed = True

    # Check with shellcheck
    shellcheck = shutil.which("shellcheck")
    if not shellcheck:
        messages.append("shellcheck not available (skipped)")
    else:
        result = subprocess.run(
            ["shellcheck", str(script)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            all_passed = False
            messages.append(f"shellcheck failed:\n{result.stderr}\n{result.stdout}")
        else:
            messages.append("shellcheck: OK")

    # Check formatting with shfmt
    if check_formatting:
        shfmt = shutil.which("shfmt")
        if not shfmt:
            messages.append("shfmt not available (skipped)")
        else:
            # Run shfmt in diff mode to check if formatting would change
            result = subprocess.run(
                ["shfmt", "-d", str(script)],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                all_passed = False
                messages.append(f"shfmt formatting needed:\n{result.stdout}")
            else:
                messages.append("shfmt: OK")

    return ValidationResult(all_passed, "\n".join(messages))


def validate_justfile(justfile: Path) -> ValidationResult:
    """Validate Justfile syntax."""
    just = shutil.which("just")
    if not just:
        return ValidationResult(True, "just not available (skipped)")

    result = subprocess.run(
        ["just", "--justfile", str(justfile), "--summary"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return ValidationResult(False, f"just validation failed:\n{result.stderr}")

    return ValidationResult(True, "just: OK")


def validate_file(file_path: Path) -> ValidationResult:
    """
    Validate a file based on its type.

    Automatically detects file type and runs appropriate validators.

    Args:
        file_path: Path to file to validate

    Returns:
        ValidationResult with combined results of all checks
    """
    if not file_path.exists():
        return ValidationResult(False, f"File does not exist: {file_path}")

    messages = []
    all_passed = True

    # Check consecutive blank lines first
    blank_result = validate_no_consecutive_blank_lines(file_path)
    if not blank_result:
        all_passed = False
    messages.append(str(blank_result))

    # Type-specific validation
    filename = file_path.name.lower()

    if filename.endswith((".yaml", ".yml")):
        result = validate_yaml(file_path)
        if not result:
            all_passed = False
        messages.append(str(result))

    elif filename == "dockerfile":
        result = validate_dockerfile(file_path)
        if not result:
            all_passed = False
        messages.append(str(result))

    elif filename.endswith(".sh"):
        result = validate_shell_script(file_path)
        if not result:
            all_passed = False
        messages.append(str(result))

    elif filename == "justfile":
        result = validate_justfile(file_path)
        if not result:
            all_passed = False
        messages.append(str(result))

    return ValidationResult(all_passed, "\n".join(messages))


def validate_directory(
    directory: Path, patterns: List[str] = None
) -> dict[Path, ValidationResult]:
    """
    Validate all files in a directory matching patterns.

    Args:
        directory: Directory to scan
        patterns: List of glob patterns to match (default: all common generated files)

    Returns:
        Dictionary mapping file paths to validation results
    """
    if patterns is None:
        patterns = [
            "*.yaml",
            "*.yml",
            "Dockerfile",
            "*.sh",
            "Justfile",
        ]

    results = {}
    for pattern in patterns:
        for file_path in directory.glob(pattern):
            if file_path.is_file():
                results[file_path] = validate_file(file_path)

    return results
