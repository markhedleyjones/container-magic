"""Tests for pip step handling.

Pip packages install directly into the base image's Python, not into a venv.
The only setup needed is removing the PEP 668 EXTERNALLY-MANAGED marker when
present (Debian/Ubuntu with apt-installed Python), which is a host-system
protection that doesn't apply inside containers.
"""

from tests.unit.conftest import generate_dockerfile_from_dict as _generate


def _base_config(**overrides):
    """Minimal config with overrides applied to the base stage."""
    config = {
        "names": {"image": "test", "workspace": "workspace", "user": "root"},
        "stages": {
            "base": {"from": "debian:bookworm-slim", **overrides},
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    return config


class TestPipPreparation:
    def test_pip_as_root_removes_marker(self):
        """First pip step as root injects marker removal, no USER switch."""
        config = _base_config(steps=[{"pip": {"install": ["numpy"]}}])
        content = _generate(config)
        assert "EXTERNALLY-MANAGED" in content
        # No venv anywhere
        assert "/opt/venv" not in content
        assert "VIRTUAL_ENV" not in content
        # No USER root before the marker removal line (already root)
        lines = content.splitlines()
        mm_idx = next(i for i, line in enumerate(lines) if "EXTERNALLY-MANAGED" in line)
        preceding = [line.strip() for line in lines[:mm_idx] if line.strip()]
        assert preceding[-1] != "USER root"

    def test_pip_after_become_user_switches_to_root(self):
        """Pip step after become: user injects USER root / USER restore."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "appuser"},
            "stages": {
                "base": {
                    "from": "debian:bookworm-slim",
                    "steps": [
                        {"create": "user"},
                        {"become": "user"},
                        {"pip": {"install": ["flask"]}},
                    ],
                },
                "development": {"from": "base"},
                "production": {"from": "base"},
            },
        }
        content = _generate(config)
        lines = content.splitlines()
        mm_idx = next(i for i, line in enumerate(lines) if "# Disable PEP 668" in line)
        # USER root should appear in the prelude for the prepare_pip block
        preceding = [line.strip() for line in lines[:mm_idx] if line.strip()]
        # Walk back to find the nearest USER directive or other action
        user_lines = [line for line in preceding if line.startswith("USER ")]
        assert user_lines[-1] == "USER root"
        # USER restore should come after the RUN rm line
        trailing = [line.strip() for line in lines[mm_idx + 1 :] if line.strip()]
        restore_user = next(line for line in trailing if line.startswith("USER "))
        assert restore_user != "USER root"

    def test_child_stage_skips_duplicate_marker_removal(self):
        """Pip in child stage does not re-emit marker removal if parent did."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "appuser"},
            "stages": {
                "base": {
                    "from": "debian:bookworm-slim",
                    "steps": [
                        {"pip": {"install": ["numpy"]}},
                        {"create": "user"},
                    ],
                },
                "development": {
                    "from": "base",
                    "steps": [
                        {"become": "user"},
                        {"pip": {"install": ["pytest"]}},
                    ],
                },
                "production": {"from": "base"},
            },
        }
        content = _generate(config)
        assert content.count("# Disable PEP 668") == 1

    def test_child_stage_with_new_base_removes_marker(self):
        """Pip in child stage without parent pip re-emits marker removal."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "appuser"},
            "stages": {
                "base": {
                    "from": "debian:bookworm-slim",
                    "steps": [{"create": "user"}],
                },
                "development": {
                    "from": "base",
                    "steps": [
                        {"become": "user"},
                        {"pip": {"install": ["pytest"]}},
                    ],
                },
                "production": {"from": "base"},
            },
        }
        content = _generate(config)
        assert "EXTERNALLY-MANAGED" in content

    def test_no_pip_steps_no_marker_removal(self):
        """No marker removal when no pip steps exist."""
        config = _base_config(steps=[{"run": "echo hello"}])
        content = _generate(config)
        assert "EXTERNALLY-MANAGED" not in content

    def test_multiple_pip_steps_single_marker_removal(self):
        """Multiple pip steps in the same stage only trigger marker removal once."""
        config = _base_config(
            steps=[
                {"pip": {"install": ["numpy"]}},
                {"pip": {"install": ["flask"]}},
            ]
        )
        content = _generate(config)
        assert content.count("# Disable PEP 668") == 1
        # Both pip installs should appear
        assert content.count("pip install --no-cache-dir") == 2

    def test_pip_single_package_string(self):
        """Pip step with single package as string (not list) works."""
        config = _base_config(steps=[{"pip": {"install": "requests"}}])
        content = _generate(config)
        assert "EXTERNALLY-MANAGED" in content
        assert "requests" in content

    def test_become_without_create_user(self):
        """Pip after become to a pre-existing user (no create step) wraps with USER root."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "root"},
            "stages": {
                "base": {
                    "from": "debian:bookworm-slim",
                    "steps": [
                        {"become": "www-data"},
                        {"pip": {"install": ["flask"]}},
                    ],
                },
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
            },
        }
        content = _generate(config)
        assert "USER root" in content
        assert "USER www-data" in content
        assert "EXTERNALLY-MANAGED" in content

    def test_stage_from_external_image_removes_marker_again(self):
        """Stage from a separate external image starts fresh and removes marker again."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "root"},
            "stages": {
                "builder": {
                    "from": "debian:bookworm-slim",
                    "steps": [{"pip": {"install": ["build"]}}],
                },
                "base": {
                    "from": "debian:bookworm-slim",
                    "steps": [{"pip": {"install": ["requests"]}}],
                },
                "development": {"from": "base"},
                "production": {"from": "base"},
            },
        }
        content = _generate(config)
        # Two independent FROM chains, each needs its own marker removal.
        assert content.count("# Disable PEP 668") == 2

    def test_no_opt_venv_anywhere(self):
        """/opt/venv is no longer part of generated Dockerfiles."""
        config = _base_config(steps=[{"pip": {"install": ["flask"]}}])
        content = _generate(config)
        assert "/opt/venv" not in content
        assert "VIRTUAL_ENV" not in content
        assert "python3 -m venv" not in content


class TestCompileBytecode:
    def test_compileall_emitted_after_pip(self):
        """A stage with pip steps gets a compileall step after them."""
        config = _base_config(steps=[{"pip": {"install": ["flask"]}}])
        content = _generate(config)
        assert "python3 -m compileall" in content
        # compileall should come after the pip install
        lines = content.splitlines()
        pip_idx = next(i for i, ln in enumerate(lines) if "pip install" in ln)
        compile_idx = next(i for i, ln in enumerate(lines) if "compileall" in ln)
        assert compile_idx > pip_idx

    def test_no_compileall_without_pip(self):
        """Stages without pip don't emit compileall."""
        config = _base_config(steps=[{"run": "echo hello"}])
        content = _generate(config)
        assert "compileall" not in content

    def test_compileall_per_stage_that_adds_pip(self):
        """Each stage that adds pip packages gets its own compileall."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "appuser"},
            "stages": {
                "base": {
                    "from": "debian:bookworm-slim",
                    "steps": [{"pip": {"install": ["flask"]}}],
                },
                "development": {
                    "from": "base",
                    "steps": [{"pip": {"install": ["pytest"]}}],
                },
                "production": {"from": "base"},
            },
        }
        content = _generate(config)
        # Base and development both add pip, both get compileall.
        # Production inherits without adding - no compileall.
        assert content.count("python3 -m compileall") == 2

    def test_compileall_triggered_by_conda(self):
        """conda install triggers compileall just like pip does."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "root"},
            "stages": {
                "base": {
                    "from": "pytorch/pytorch:latest",
                    "steps": [{"conda": {"install": ["whisperx"]}}],
                },
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
            },
        }
        content = _generate(config)
        assert "python3 -m compileall" in content
        # Also marker removal should be injected for conda
        assert "# Disable PEP 668" in content

    def test_compileall_triggered_by_mamba(self):
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "root"},
            "stages": {
                "base": {
                    "from": "pytorch/pytorch:latest",
                    "steps": [{"mamba": {"install": ["whisperx"]}}],
                },
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
            },
        }
        content = _generate(config)
        assert "python3 -m compileall" in content

    def test_no_compileall_for_apt_only_stage(self):
        """apt-get installs don't trigger compileall (not a Python installer)."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "root"},
            "stages": {
                "base": {
                    "from": "debian:bookworm-slim",
                    "steps": [{"apt-get": {"install": ["curl"]}}],
                },
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
            },
        }
        content = _generate(config)
        assert "compileall" not in content

    def test_compileall_wraps_user_when_not_root(self):
        """If end-of-stage user context is non-root, wrap with USER root."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "appuser"},
            "stages": {
                "base": {
                    "from": "debian:bookworm-slim",
                    "steps": [
                        {"pip": {"install": ["flask"]}},
                        {"create": "user"},
                        {"become": "user"},
                    ],
                },
                "development": {"from": "base"},
                "production": {"from": "base"},
            },
        }
        content = _generate(config)
        lines = content.splitlines()
        compile_idx = next(i for i, ln in enumerate(lines) if "compileall" in ln)
        preceding = [line.strip() for line in lines[:compile_idx] if line.strip()]
        user_lines = [line for line in preceding if line.startswith("USER ")]
        assert user_lines[-1] == "USER root"
