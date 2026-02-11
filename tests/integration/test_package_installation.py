"""Integration tests for package installation across different base images."""

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


def get_runtime():
    """Detect available container runtime (docker or podman)."""
    for runtime in ["docker", "podman"]:
        try:
            subprocess.run(
                [runtime, "--version"],
                capture_output=True,
                timeout=5,
                check=True,
            )
            return runtime
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    pytest.skip("No container runtime found (docker or podman)")


def run_command(cmd, cwd, timeout=300):
    """Run command and return output."""
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


@pytest.mark.slow
def test_package_installation_python_slim():
    """Test that packages install and are accessible in python:3.11-slim base."""
    runtime = get_runtime()
    config = """
project:
  name: test-python
  workspace: workspace

stages:
  base:
    from: python:3.11-slim
    packages:
      apt: [curl]
  development:
    from: base
  production:
    from: base
"""

    with TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Write config
        (tmpdir_path / "cm.yaml").write_text(config)

        # Create empty workspace
        (tmpdir_path / "workspace").mkdir()
        (tmpdir_path / "workspace" / "test.txt").write_text("test")

        # Generate files
        returncode, stdout, stderr = run_command(["cm", "update"], tmpdir_path)
        assert returncode == 0, f"cm update failed: {stderr}"

        # Build the image
        returncode, stdout, stderr = run_command(
            [runtime, "build", "-t", "test-python:latest", "."],
            tmpdir_path,
            timeout=600,
        )
        assert returncode == 0, f"{runtime} build failed: {stderr}"

        # Run curl --version in the built image
        returncode, stdout, stderr = run_command(
            [
                runtime,
                "run",
                "--rm",
                "test-python:latest",
                "curl",
                "--version",
            ],
            tmpdir_path,
        )
        assert returncode == 0, f"curl failed in container: {stderr}"
        assert "curl" in stdout.lower(), f"curl version not found in output: {stdout}"


@pytest.mark.slow
def test_package_installation_ubuntu():
    """Test that packages install and are accessible in ubuntu:22.04 base."""
    runtime = get_runtime()
    config = """
project:
  name: test-ubuntu
  workspace: workspace

stages:
  base:
    from: ubuntu:22.04
    packages:
      apt: [curl, ca-certificates]
  development:
    from: base
  production:
    from: base
"""

    with TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Write config
        (tmpdir_path / "cm.yaml").write_text(config)

        # Create empty workspace
        (tmpdir_path / "workspace").mkdir()
        (tmpdir_path / "workspace" / "test.txt").write_text("test")

        # Generate files
        returncode, stdout, stderr = run_command(["cm", "update"], tmpdir_path)
        assert returncode == 0, f"cm update failed: {stderr}"

        # Build the image
        returncode, stdout, stderr = run_command(
            [runtime, "build", "-t", "test-ubuntu:latest", "."],
            tmpdir_path,
            timeout=600,
        )
        assert returncode == 0, f"{runtime} build failed: {stderr}"

        # Run curl --version in the built image
        returncode, stdout, stderr = run_command(
            [
                runtime,
                "run",
                "--rm",
                "test-ubuntu:latest",
                "curl",
                "--version",
            ],
            tmpdir_path,
        )
        assert returncode == 0, f"curl failed in container: {stderr}"
        assert "curl" in stdout.lower(), f"curl version not found in output: {stdout}"


@pytest.mark.slow
def test_package_installation_debian():
    """Test that packages install and are accessible in debian:bookworm base."""
    runtime = get_runtime()
    config = """
project:
  name: test-debian
  workspace: workspace

stages:
  base:
    from: debian:bookworm
    packages:
      apt: [curl]
  development:
    from: base
  production:
    from: base
"""

    with TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Write config
        (tmpdir_path / "cm.yaml").write_text(config)

        # Create empty workspace
        (tmpdir_path / "workspace").mkdir()
        (tmpdir_path / "workspace" / "test.txt").write_text("test")

        # Generate files
        returncode, stdout, stderr = run_command(["cm", "update"], tmpdir_path)
        assert returncode == 0, f"cm update failed: {stderr}"

        # Build the image
        returncode, stdout, stderr = run_command(
            [runtime, "build", "-t", "test-debian:latest", "."],
            tmpdir_path,
            timeout=600,
        )
        assert returncode == 0, f"{runtime} build failed: {stderr}"

        # Run curl --version in the built image
        returncode, stdout, stderr = run_command(
            [
                runtime,
                "run",
                "--rm",
                "test-debian:latest",
                "curl",
                "--version",
            ],
            tmpdir_path,
        )
        assert returncode == 0, f"curl failed in container: {stderr}"
        assert "curl" in stdout.lower(), f"curl version not found in output: {stdout}"


@pytest.mark.slow
def test_package_installation_alpine():
    """Test that packages install and are accessible in alpine:latest base."""
    runtime = get_runtime()
    config = """
project:
  name: test-alpine
  workspace: workspace

stages:
  base:
    from: alpine:latest
    packages:
      apk: [curl]
  development:
    from: base
  production:
    from: base
"""

    with TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Write config
        (tmpdir_path / "cm.yaml").write_text(config)

        # Create empty workspace
        (tmpdir_path / "workspace").mkdir()
        (tmpdir_path / "workspace" / "test.txt").write_text("test")

        # Generate files
        returncode, stdout, stderr = run_command(["cm", "update"], tmpdir_path)
        assert returncode == 0, f"cm update failed: {stderr}"

        # Build the image
        returncode, stdout, stderr = run_command(
            [runtime, "build", "-t", "test-alpine:latest", "."],
            tmpdir_path,
            timeout=600,
        )
        assert returncode == 0, f"{runtime} build failed: {stderr}"

        # Run curl --version in the built image
        returncode, stdout, stderr = run_command(
            [
                runtime,
                "run",
                "--rm",
                "test-alpine:latest",
                "curl",
                "--version",
            ],
            tmpdir_path,
        )
        assert returncode == 0, f"curl failed in container: {stderr}"
        assert "curl" in stdout.lower(), f"curl version not found in output: {stdout}"


@pytest.mark.slow
def test_package_installation_ubuntu_24_04():
    """Test that packages install and are accessible in ubuntu:24.04 base."""
    runtime = get_runtime()
    config = """
project:
  name: test-ubuntu-24
  workspace: workspace

stages:
  base:
    from: ubuntu:24.04
    packages:
      apt: [curl, ca-certificates]
  development:
    from: base
  production:
    from: base
"""

    with TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Write config
        (tmpdir_path / "cm.yaml").write_text(config)

        # Create empty workspace
        (tmpdir_path / "workspace").mkdir()
        (tmpdir_path / "workspace" / "test.txt").write_text("test")

        # Generate files
        returncode, stdout, stderr = run_command(["cm", "update"], tmpdir_path)
        assert returncode == 0, f"cm update failed: {stderr}"

        # Build the image
        returncode, stdout, stderr = run_command(
            [runtime, "build", "-t", "test-ubuntu-24:latest", "."],
            tmpdir_path,
            timeout=600,
        )
        assert returncode == 0, f"{runtime} build failed: {stderr}"

        # Run curl --version in the built image
        returncode, stdout, stderr = run_command(
            [
                runtime,
                "run",
                "--rm",
                "test-ubuntu-24:latest",
                "curl",
                "--version",
            ],
            tmpdir_path,
        )
        assert returncode == 0, f"curl failed in container: {stderr}"
        assert "curl" in stdout.lower(), f"curl version not found in output: {stdout}"


@pytest.mark.slow
def test_multiple_packages_installation():
    """Test that multiple packages install and are accessible."""
    runtime = get_runtime()
    config = """
project:
  name: test-multi
  workspace: workspace

stages:
  base:
    from: python:3.11-slim
    packages:
      apt: [curl, git, ca-certificates]
  development:
    from: base
  production:
    from: base
"""

    with TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Write config
        (tmpdir_path / "cm.yaml").write_text(config)

        # Create empty workspace
        (tmpdir_path / "workspace").mkdir()
        (tmpdir_path / "workspace" / "test.txt").write_text("test")

        # Generate files
        returncode, stdout, stderr = run_command(["cm", "update"], tmpdir_path)
        assert returncode == 0, f"cm update failed: {stderr}"

        # Build the image
        returncode, stdout, stderr = run_command(
            [runtime, "build", "-t", "test-multi:latest", "."],
            tmpdir_path,
            timeout=600,
        )
        assert returncode == 0, f"{runtime} build failed: {stderr}"

        # Test curl
        returncode, stdout, stderr = run_command(
            [
                runtime,
                "run",
                "--rm",
                "test-multi:latest",
                "curl",
                "--version",
            ],
            tmpdir_path,
        )
        assert returncode == 0, f"curl failed: {stderr}"
        assert "curl" in stdout.lower()

        # Test git
        returncode, stdout, stderr = run_command(
            [
                runtime,
                "run",
                "--rm",
                "test-multi:latest",
                "git",
                "--version",
            ],
            tmpdir_path,
        )
        assert returncode == 0, f"git failed: {stderr}"
        assert "git" in stdout.lower()
