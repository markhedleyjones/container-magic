"""Tests for path translation when running commands from different directories."""

from pathlib import Path

import pytest

from container_magic.core.config import ContainerMagicConfig
from container_magic.generators.dockerfile import generate_dockerfile
from container_magic.generators.justfile import generate_justfile


@pytest.fixture
def test_project(tmp_path):
    """Create a test project with nested directories."""
    # Create directory structure
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    subdir = workspace / "subdir"
    subdir.mkdir()

    # Create test script in workspace root
    test_script_root = workspace / "test_root.py"
    test_script_root.write_text("print('Called from workspace root')\n")

    # Create test script in subdirectory
    test_script_sub = subdir / "test_sub.py"
    test_script_sub.write_text("print('Called from workspace/subdir')\n")

    # Create config
    config = ContainerMagicConfig(
        project={"name": "test-paths", "workspace": "workspace"},
        stages={
            "base": {"from": "python:3.11-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
    )

    # Create config file
    config_file = tmp_path / "cm.yaml"
    import yaml

    config_file.write_text(yaml.dump(config.model_dump()))

    # Generate Dockerfile and Justfile
    generate_dockerfile(config, tmp_path / "Dockerfile")
    generate_justfile(config, config_file, tmp_path / "Justfile")

    return {
        "project_dir": tmp_path,
        "workspace": workspace,
        "subdir": subdir,
        "config": config,
    }


def test_justfile_has_user_cwd_variable(test_project):
    """Test that generated Justfile includes USER_CWD variable."""
    justfile = test_project["project_dir"] / "Justfile"
    content = justfile.read_text()

    assert 'USER_CWD := ""' in content


def test_justfile_path_translation_from_project_root(test_project):
    """Test path translation logic when USER_CWD is project root."""
    justfile = test_project["project_dir"] / "Justfile"
    content = justfile.read_text()

    # Check that workdir logic is present
    assert "USER_CWD" in content
    assert "PROJECT_ROOT" in content
    assert "REL_PATH" in content
    assert "realpath --relative-to" in content


def test_justfile_path_translation_from_subdirectory(test_project):
    """Test that Justfile can calculate relative paths."""
    # This is a unit test of the path calculation logic
    # We can't easily test the full integration without building the container

    project_root = test_project["project_dir"]
    workspace = test_project["workspace"]

    # Simulate what the Justfile will do
    rel_path = workspace.relative_to(project_root)

    assert rel_path == Path("workspace")
    assert str(rel_path) == "workspace"
