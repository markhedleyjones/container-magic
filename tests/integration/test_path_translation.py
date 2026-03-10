"""Tests for path translation when running commands from different directories."""

from pathlib import Path


from container_magic.core.runner import _translate_workdir


def test_translate_workdir_from_project_root():
    """Test path translation when user is at project root."""
    project_dir = Path("/home/user/project")
    user_cwd = Path("/home/user/project")
    container_home = "/home/user"

    result = _translate_workdir(project_dir, user_cwd, container_home)
    assert result == "/home/user"


def test_translate_workdir_from_workspace():
    """Test path translation when user is inside workspace."""
    project_dir = Path("/home/user/project")
    user_cwd = Path("/home/user/project/workspace")
    container_home = "/home/user"

    result = _translate_workdir(project_dir, user_cwd, container_home)
    assert result == "/home/user/workspace"


def test_translate_workdir_from_nested_subdir():
    """Test path translation when user is in a nested subdirectory."""
    project_dir = Path("/home/user/project")
    user_cwd = Path("/home/user/project/workspace/subdir")
    container_home = "/home/user"

    result = _translate_workdir(project_dir, user_cwd, container_home)
    assert result == "/home/user/workspace/subdir"


def test_translate_workdir_from_outside_project():
    """Test path translation when user cwd is outside project."""
    project_dir = Path("/home/user/project")
    user_cwd = Path("/tmp/somewhere")
    container_home = "/home/user"

    result = _translate_workdir(project_dir, user_cwd, container_home)
    assert result == "/home/user"
