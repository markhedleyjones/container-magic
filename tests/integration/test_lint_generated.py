"""Lint-check generated Dockerfiles and shell scripts across config variations.

Ensures that container-magic produces output that passes hadolint (Dockerfiles)
and shellcheck + shfmt (shell scripts) for a wide range of configurations.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from container_magic.core.config import ContainerMagicConfig
from container_magic.generators.build_script import generate_build_script
from container_magic.generators.dockerfile import generate_dockerfile
from container_magic.generators.run_script import generate_run_script

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "configs"
HADOLINT_CONFIG = Path(__file__).parent.parent / "fixtures" / "hadolint.yaml"

# All fixture configs to test
FIXTURE_CONFIGS = sorted(FIXTURES_DIR.glob("*.yaml"))

# Tool availability
HAS_HADOLINT = shutil.which("hadolint") is not None
HAS_SHELLCHECK = shutil.which("shellcheck") is not None
HAS_SHFMT = shutil.which("shfmt") is not None


def _generate_files(config_path: Path, output_dir: Path):
    """Generate Dockerfile, build.sh, and run.sh from a config file."""
    config = ContainerMagicConfig.from_yaml(config_path)

    # Create workspace directory (required by generator)
    workspace_dir = output_dir / config.names.workspace
    workspace_dir.mkdir(exist_ok=True)

    generate_dockerfile(config, output_dir / "Dockerfile")
    generate_build_script(config, output_dir)
    generate_run_script(config, output_dir)


@pytest.fixture(
    params=[p.stem for p in FIXTURE_CONFIGS], ids=[p.stem for p in FIXTURE_CONFIGS]
)
def generated_project(request, tmp_path):
    """Generate a project from each fixture config into a temp directory."""
    config_name = request.param
    config_path = FIXTURES_DIR / f"{config_name}.yaml"

    # Copy config to temp dir and generate
    shutil.copy(config_path, tmp_path / "cm.yaml")
    _generate_files(tmp_path / "cm.yaml", tmp_path)

    return tmp_path


class TestDockerfileLinting:
    @pytest.mark.skipif(not HAS_HADOLINT, reason="hadolint not installed")
    def test_hadolint_passes(self, generated_project):
        """Generated Dockerfile passes hadolint with no warnings (ignoring user-content rules)."""
        dockerfile = generated_project / "Dockerfile"
        result = subprocess.run(
            [
                "hadolint",
                "--config",
                str(HADOLINT_CONFIG),
                "--failure-threshold",
                "warning",
                str(dockerfile),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"hadolint found issues:\n{result.stdout}\n{result.stderr}"
        )


class TestShellScriptLinting:
    @pytest.mark.skipif(not HAS_SHELLCHECK, reason="shellcheck not installed")
    def test_shellcheck_build_sh(self, generated_project):
        """Generated build.sh passes shellcheck."""
        result = subprocess.run(
            ["shellcheck", str(generated_project / "build.sh")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"shellcheck build.sh:\n{result.stdout}\n{result.stderr}"
        )

    @pytest.mark.skipif(not HAS_SHELLCHECK, reason="shellcheck not installed")
    def test_shellcheck_run_sh(self, generated_project):
        """Generated run.sh passes shellcheck."""
        result = subprocess.run(
            ["shellcheck", str(generated_project / "run.sh")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"shellcheck run.sh:\n{result.stdout}\n{result.stderr}"
        )

    @pytest.mark.skipif(not HAS_SHFMT, reason="shfmt not installed")
    def test_shfmt_build_sh(self, generated_project):
        """Generated build.sh needs no formatting changes."""
        result = subprocess.run(
            ["shfmt", "-d", str(generated_project / "build.sh")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"shfmt build.sh formatting diff:\n{result.stdout}"
        )

    @pytest.mark.skipif(not HAS_SHFMT, reason="shfmt not installed")
    def test_shfmt_run_sh(self, generated_project):
        """Generated run.sh needs no formatting changes."""
        result = subprocess.run(
            ["shfmt", "-d", str(generated_project / "run.sh")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"shfmt run.sh formatting diff:\n{result.stdout}"


@pytest.fixture(
    params=["single_symlink", "multiple_symlinks", "nested_symlink"],
    ids=["single_symlink", "multiple_symlinks", "nested_symlink"],
)
def generated_project_with_symlinks(request, tmp_path):
    """Generate a project with workspace symlinks for linting."""
    config_dict = {
        "names": {
            "image": "test-symlinks",
            "workspace": "workspace",
            "user": "appuser",
        },
        "stages": {
            "base": {
                "from": "python:3-slim",
                "steps": [{"create": "user"}, {"become": "user"}],
            },
            "development": {"from": "base"},
            "production": {
                "from": "base",
                "steps": [{"become": "user"}, {"copy": "workspace"}],
            },
        },
    }
    config = ContainerMagicConfig(**config_dict)
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    if request.param == "single_symlink":
        ext = tmp_path / "external_lib"
        ext.mkdir()
        (ext / "data.py").write_text("pass")
        (workspace / "lib").symlink_to(ext)
    elif request.param == "multiple_symlinks":
        for name in ["alpha", "beta", "gamma"]:
            ext = tmp_path / f"ext_{name}"
            ext.mkdir()
            (ext / "module.py").write_text("pass")
            (workspace / name).symlink_to(ext)
    elif request.param == "nested_symlink":
        ext = tmp_path / "shared_data"
        ext.mkdir()
        (ext / "config.json").write_text("{}")
        (workspace / "src" / "vendor").mkdir(parents=True)
        (workspace / "src" / "vendor" / "shared").symlink_to(ext)

    from container_magic.core.symlinks import scan_workspace_symlinks

    symlinks = scan_workspace_symlinks(workspace)
    generate_dockerfile(config, tmp_path / "Dockerfile", workspace_symlinks=symlinks)
    generate_build_script(config, tmp_path, workspace_symlinks=symlinks)
    generate_run_script(config, tmp_path)

    return tmp_path


class TestSymlinkLinting:
    """Lint generated files when workspace symlinks trigger staging code paths."""

    @pytest.mark.skipif(not HAS_HADOLINT, reason="hadolint not installed")
    def test_hadolint_passes(self, generated_project_with_symlinks):
        dockerfile = generated_project_with_symlinks / "Dockerfile"
        result = subprocess.run(
            [
                "hadolint",
                "--config",
                str(HADOLINT_CONFIG),
                "--failure-threshold",
                "warning",
                str(dockerfile),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"hadolint found issues:\n{result.stdout}\n{result.stderr}"
        )

    @pytest.mark.skipif(not HAS_SHELLCHECK, reason="shellcheck not installed")
    def test_shellcheck_build_sh(self, generated_project_with_symlinks):
        result = subprocess.run(
            ["shellcheck", str(generated_project_with_symlinks / "build.sh")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"shellcheck build.sh:\n{result.stdout}\n{result.stderr}"
        )

    @pytest.mark.skipif(not HAS_SHFMT, reason="shfmt not installed")
    def test_shfmt_build_sh(self, generated_project_with_symlinks):
        result = subprocess.run(
            ["shfmt", "-d", str(generated_project_with_symlinks / "build.sh")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"shfmt build.sh formatting diff:\n{result.stdout}"
        )

    def test_no_consecutive_blank_lines(self, generated_project_with_symlinks):
        for filename in ["Dockerfile", "build.sh"]:
            filepath = generated_project_with_symlinks / filename
            lines = filepath.read_text().splitlines()
            consecutive = 0
            for i, line in enumerate(lines, 1):
                if line.strip() == "":
                    consecutive += 1
                    assert consecutive <= 1, (
                        f"{filename} has consecutive blank lines at line {i}"
                    )
                else:
                    consecutive = 0


class TestNoExcessiveBlankLines:
    def test_no_consecutive_blank_lines(self, generated_project):
        """No generated file has more than one consecutive blank line."""
        for filename in ["Dockerfile", "build.sh", "run.sh"]:
            filepath = generated_project / filename
            if not filepath.exists():
                continue
            lines = filepath.read_text().splitlines()
            consecutive = 0
            for i, line in enumerate(lines, 1):
                if line.strip() == "":
                    consecutive += 1
                    assert consecutive <= 1, (
                        f"{filename} has consecutive blank lines at line {i}"
                    )
                else:
                    consecutive = 0
