"""Tests for implicit user creation and become."""

from tests.unit.conftest import generate_dockerfile_from_dict as _generate
from tests.unit.conftest import get_stage_block as _get_stage_block


class TestImplicitCreateUser:
    def test_non_root_user_gets_implicit_creation(self):
        """names.user != root should inject create_user in from-image stages."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "appuser"},
            "stages": {
                "base": {
                    "from": "debian:bookworm-slim",
                    "steps": [{"run": "echo hello"}],
                },
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
            },
        }
        content = _generate(config)
        assert "useradd" in content or "adduser" in content

    def test_root_user_no_implicit_creation(self):
        """names.user == root should not inject any user creation."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "root"},
            "stages": {
                "base": {
                    "from": "debian:bookworm-slim",
                    "steps": [{"run": "echo hello"}],
                },
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
            },
        }
        content = _generate(config)
        assert "useradd" not in content
        assert "adduser" not in content

    def test_explicit_create_skips_implicit(self):
        """Explicit {create: user} prevents double creation."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "appuser"},
            "stages": {
                "base": {
                    "from": "debian:bookworm-slim",
                    "steps": [{"create": "user"}, {"run": "echo hello"}],
                },
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
            },
        }
        content = _generate(config)
        # Only one user creation block (the explicit one, not doubled)
        create_count = content.count("useradd") + content.count("adduser -D")
        assert create_count == 1

    def test_multi_stage_each_image_stage_gets_creation(self):
        """Each from-image stage gets its own user creation."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "appuser"},
            "stages": {
                "builder": {"from": "debian:bookworm-slim", "steps": []},
                "base": {"from": "debian:bookworm-slim", "steps": []},
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
            },
        }
        content = _generate(config)
        # Both builder and base are from external images, both get user creation
        create_count = content.count("Create user account")
        assert create_count == 2

    def test_mixed_explicit_and_implicit_across_stages(self):
        """One from-image stage explicit, another implicit - both create correctly."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "appuser"},
            "stages": {
                "builder": {
                    "from": "debian:bookworm-slim",
                    "steps": [{"create": "user"}],
                },
                "base": {"from": "debian:bookworm-slim", "steps": []},
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
            },
        }
        content = _generate(config)
        # Both should create the user (builder explicit, base implicit)
        create_count = content.count("Create user account")
        assert create_count == 2

    def test_child_stage_no_duplicate_creation(self):
        """Child stages inheriting from a parent don't re-create the user."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "appuser"},
            "stages": {
                "base": {"from": "debian:bookworm-slim", "steps": []},
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
            },
        }
        content = _generate(config)
        # Only one creation (in base), not in dev or prod
        create_count = content.count("Create user account")
        assert create_count == 1


class TestImplicitBecome:
    def test_non_root_gets_implicit_become_at_end_of_leaf_stages(self):
        """Leaf stages should end with USER directive, intermediate stages should not."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "appuser"},
            "stages": {
                "base": {
                    "from": "debian:bookworm-slim",
                    "steps": [{"run": "echo hello"}],
                },
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
            },
        }
        content = _generate(config)
        # Leaf stages (development, production) get implicit USER
        for stage in ["development", "production"]:
            block = _get_stage_block(content, stage)
            lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
            assert lines[-1].startswith("USER "), f"Stage {stage} should end with USER"
        # Intermediate stage (base) should NOT end with USER
        base_block = _get_stage_block(content, "base")
        base_lines = [ln.strip() for ln in base_block.splitlines() if ln.strip()]
        assert not base_lines[-1].startswith("USER "), (
            "Intermediate stage should not end with USER"
        )

    def test_explicit_become_at_end_not_duplicated(self):
        """If stage already ends with become: user, don't add another."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "appuser"},
            "stages": {
                "base": {
                    "from": "debian:bookworm-slim",
                    "steps": [{"run": "echo hello"}, {"become": "user"}],
                },
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
            },
        }
        content = _generate(config)
        base = _get_stage_block(content, "base")
        user_lines = [ln for ln in base.splitlines() if ln.strip().startswith("USER ")]
        assert len(user_lines) == 1

    def test_explicit_become_root_at_end_preserved(self):
        """If stage ends with become: root, no implicit become is added."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "appuser"},
            "stages": {
                "base": {
                    "from": "debian:bookworm-slim",
                    "steps": [{"run": "echo hello"}, {"become": "root"}],
                },
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
            },
        }
        content = _generate(config)
        base = _get_stage_block(content, "base")
        lines = [ln.strip() for ln in base.splitlines() if ln.strip()]
        assert lines[-1] == "USER root"

    def test_root_user_no_implicit_become(self):
        """names.user == root should not add any USER directives."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "root"},
            "stages": {
                "base": {
                    "from": "debian:bookworm-slim",
                    "steps": [{"run": "echo hello"}],
                },
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
            },
        }
        content = _generate(config)
        assert "USER " not in content

    def test_production_workspace_is_root_owned(self):
        """Production workspace should be root-owned (no --chown) for immutability."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "appuser"},
            "stages": {
                "base": {"from": "debian:bookworm-slim", "steps": []},
                "development": {"from": "base", "steps": []},
                "production": {
                    "from": "base",
                    "steps": [{"copy": "workspace"}],
                },
            },
        }
        content = _generate(config)
        prod = _get_stage_block(content, "production")
        lines = [ln.strip() for ln in prod.splitlines() if ln.strip()]
        copy_lines = [ln for ln in lines if "COPY" in ln and "workspace" in ln]
        assert len(copy_lines) == 1
        assert "--chown" not in copy_lines[0]
        assert lines[-1].startswith("USER ")

    def test_explicit_become_before_copy_gives_chown(self):
        """Explicit become before copy: workspace makes files user-owned."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "appuser"},
            "stages": {
                "base": {"from": "debian:bookworm-slim", "steps": []},
                "development": {"from": "base", "steps": []},
                "production": {
                    "from": "base",
                    "steps": [{"become": "user"}, {"copy": "workspace"}],
                },
            },
        }
        content = _generate(config)
        prod = _get_stage_block(content, "production")
        copy_lines = [
            ln.strip() for ln in prod.splitlines() if "COPY" in ln and "workspace" in ln
        ]
        assert len(copy_lines) == 1
        assert "--chown" in copy_lines[0]

    def test_stage_demotion_removes_implicit_become(self):
        """Adding a child to a leaf stage demotes it, removing implicit become."""
        # Config where testing is a leaf (no children)
        config_leaf = {
            "names": {"image": "test", "workspace": "workspace", "user": "appuser"},
            "stages": {
                "base": {"from": "debian:bookworm-slim", "steps": []},
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
                "testing": {"from": "base", "steps": [{"run": "echo test"}]},
            },
        }
        content_leaf = _generate(config_leaf)
        testing_block = _get_stage_block(content_leaf, "testing")
        testing_lines = [ln.strip() for ln in testing_block.splitlines() if ln.strip()]
        assert testing_lines[-1].startswith("USER "), (
            "Leaf testing stage should have USER"
        )

        # Config where testing has a child (now intermediate)
        config_intermediate = {
            "names": {"image": "test", "workspace": "workspace", "user": "appuser"},
            "stages": {
                "base": {"from": "debian:bookworm-slim", "steps": []},
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
                "testing": {"from": "base", "steps": [{"run": "echo test"}]},
                "testing_child": {"from": "testing", "steps": []},
            },
        }
        content_intermediate = _generate(config_intermediate)
        testing_block = _get_stage_block(content_intermediate, "testing")
        testing_lines = [ln.strip() for ln in testing_block.splitlines() if ln.strip()]
        assert not testing_lines[-1].startswith("USER "), (
            "Intermediate testing stage should not have USER"
        )


class TestDistroInheritance:
    def test_child_inherits_distro_from_parent(self):
        """Child stage should inherit distro from parent via from: chain."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "appuser"},
            "stages": {
                "base": {"from": "myimage:latest", "distro": "alpine", "steps": []},
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
            },
        }
        content = _generate(config)
        # Base should use Alpine-style user creation (adduser not useradd)
        assert "adduser" in content
        assert "useradd" not in content

    def test_child_distro_overrides_parent(self):
        """Explicit distro on child takes precedence over parent."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "appuser"},
            "stages": {
                "base": {
                    "from": "myimage:latest",
                    "distro": "alpine",
                    "steps": [],
                },
                "other": {
                    "from": "debian:bookworm-slim",
                    "distro": "debian",
                    "steps": [],
                },
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
            },
        }
        content = _generate(config)
        base = _get_stage_block(content, "base")
        other = _get_stage_block(content, "other")
        assert "adduser" in base
        assert "useradd" in other


class TestImplicitUserWithVenv:
    def test_implicit_user_with_pip_step(self):
        """Pip step with implicit user creation should work correctly."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "appuser"},
            "stages": {
                "base": {
                    "from": "debian:bookworm-slim",
                    "steps": [{"pip": {"install": ["flask"]}}],
                },
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
            },
        }
        content = _generate(config)
        assert "useradd" in content
        assert "python3 -m venv" in content
        lines = content.splitlines()
        create_idx = next(i for i, ln in enumerate(lines) if "useradd" in ln)
        venv_idx = next(i for i, ln in enumerate(lines) if "venv" in ln and "RUN" in ln)
        assert create_idx < venv_idx
