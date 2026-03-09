"""Tests for symlink scanning and symlink-aware generation."""

from pathlib import Path


from container_magic.core.config import ContainerMagicConfig
from container_magic.core.symlinks import scan_workspace_symlinks
from container_magic.generators.build_script import generate_build_script
from container_magic.generators.dockerfile import generate_dockerfile


# ---------------------------------------------------------------------------
# Symlink scanner
# ---------------------------------------------------------------------------


class TestScanWorkspaceSymlinks:
    def test_no_symlinks(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "file.txt").write_text("hello")
        assert scan_workspace_symlinks(workspace) == []

    def test_external_symlink_detected(self, tmp_path):
        external = tmp_path / "external"
        external.mkdir()
        (external / "lib.py").write_text("code")

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "shared").symlink_to(external)

        result = scan_workspace_symlinks(workspace)
        assert result == ["shared"]

    def test_internal_relative_symlink_ignored(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "real_dir").mkdir()
        (workspace / "real_dir" / "file.txt").write_text("content")
        (workspace / "link_dir").symlink_to(Path("real_dir"))

        result = scan_workspace_symlinks(workspace)
        assert result == []

    def test_internal_absolute_symlink_warns(self, tmp_path, caplog):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        target = workspace / "real_dir"
        target.mkdir()
        (target / "file.txt").write_text("content")
        (workspace / "link_dir").symlink_to(target.resolve())

        import logging

        with caplog.at_level(logging.WARNING):
            result = scan_workspace_symlinks(workspace)

        assert result == []
        assert "absolute path" in caplog.text

    def test_dangling_symlink_skipped(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "broken").symlink_to(tmp_path / "nonexistent")

        result = scan_workspace_symlinks(workspace)
        assert result == []

    def test_nested_external_symlink(self, tmp_path):
        external = tmp_path / "libs" / "shared"
        external.mkdir(parents=True)
        (external / "module.py").write_text("code")

        workspace = tmp_path / "workspace"
        (workspace / "src" / "vendor").mkdir(parents=True)
        (workspace / "src" / "vendor" / "shared").symlink_to(external)

        result = scan_workspace_symlinks(workspace)
        assert result == ["src/vendor/shared"]

    def test_multiple_external_symlinks(self, tmp_path):
        ext_a = tmp_path / "ext_a"
        ext_a.mkdir()
        ext_b = tmp_path / "ext_b"
        ext_b.mkdir()

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "a").symlink_to(ext_a)
        (workspace / "b").symlink_to(ext_b)

        result = scan_workspace_symlinks(workspace)
        assert set(result) == {"a", "b"}

    def test_does_not_recurse_into_external_symlink(self, tmp_path):
        external = tmp_path / "external"
        external.mkdir()
        nested = tmp_path / "nested"
        nested.mkdir()
        (external / "data").symlink_to(nested)
        (external / "file.py").write_text("code")

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "shared").symlink_to(external)

        result = scan_workspace_symlinks(workspace)
        assert result == ["shared"]

    def test_nonexistent_workspace(self, tmp_path):
        result = scan_workspace_symlinks(tmp_path / "nonexistent")
        assert result == []


# ---------------------------------------------------------------------------
# Dockerfile generation with symlinks
# ---------------------------------------------------------------------------


def _generate_with_symlinks(config_dict, tmp_path, symlink_setup=None):
    """Generate a Dockerfile with optional workspace symlinks.

    symlink_setup is a callable(workspace_path, tmp_path) that creates
    symlinks and external dirs. The workspace must exist at
    tmp_path / workspace_name before calling generate_dockerfile.
    """
    config = ContainerMagicConfig(**config_dict)
    workspace_name = config.names.workspace

    workspace = tmp_path / workspace_name
    workspace.mkdir(exist_ok=True)

    if symlink_setup:
        symlink_setup(workspace, tmp_path)

    output_path = tmp_path / "Dockerfile"
    generate_dockerfile(config, output_path)
    return output_path.read_text()


class TestDockerfileSymlinks:
    def _config(self):
        return {
            "names": {"image": "test", "workspace": "workspace", "user": "app"},
            "stages": {
                "base": {
                    "from": "python:3-slim",
                    "steps": [{"create": "user"}, {"become": "user"}],
                },
                "development": {"from": "base", "steps": []},
                "production": {
                    "from": "base",
                    "steps": [{"become": "user"}, {"copy": "workspace"}],
                },
            },
        }

    def test_no_symlinks_no_staging_copies(self, tmp_path):
        content = _generate_with_symlinks(self._config(), tmp_path)
        assert ".cm-build-staging" not in content

    def test_external_symlink_adds_staging_copy(self, tmp_path):
        def setup(workspace, root):
            ext = root / "external_lib"
            ext.mkdir()
            (ext / "code.py").write_text("pass")
            (workspace / "shared").symlink_to(ext)

        content = _generate_with_symlinks(self._config(), tmp_path, setup)
        assert "COPY" in content
        assert ".cm-build-staging/shared" in content
        assert "${WORKSPACE}/shared" in content

    def test_symlink_copy_preserves_chown(self, tmp_path):
        def setup(workspace, root):
            ext = root / "ext"
            ext.mkdir()
            (workspace / "lib").symlink_to(ext)

        content = _generate_with_symlinks(self._config(), tmp_path, setup)
        # The production stage has become: user, so chown should be present
        staging_lines = [
            line for line in content.splitlines() if ".cm-build-staging" in line
        ]
        assert len(staging_lines) >= 1
        assert "--chown=" in staging_lines[0]


# ---------------------------------------------------------------------------
# Build script generation with symlinks
# ---------------------------------------------------------------------------


class TestBuildScriptSymlinks:
    def _config(self):
        return ContainerMagicConfig(
            **{
                "names": {"image": "test", "workspace": "workspace", "user": "app"},
                "stages": {
                    "base": {
                        "from": "python:3-slim",
                        "steps": [{"create": "user"}, {"become": "user"}],
                    },
                    "development": {"from": "base", "steps": []},
                    "production": {
                        "from": "base",
                        "steps": [{"copy": "workspace"}],
                    },
                },
            }
        )

    def test_no_symlinks_no_staging(self, tmp_path):
        config = self._config()
        (tmp_path / "workspace").mkdir()
        generate_build_script(config, tmp_path)
        content = (tmp_path / "build.sh").read_text()
        assert ".cm-build-staging" not in content

    def test_external_symlink_stages_in_build_script(self, tmp_path):
        config = self._config()
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        ext = tmp_path / "external"
        ext.mkdir()
        (workspace / "shared").symlink_to(ext)

        generate_build_script(config, tmp_path)
        content = (tmp_path / "build.sh").read_text()
        assert ".cm-build-staging" in content
        assert "cp -rL" in content
        assert "shared" in content
        assert "trap" in content
