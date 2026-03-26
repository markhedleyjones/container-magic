"""Tests for automatic venv creation on pip steps."""

from pathlib import Path
from tempfile import TemporaryDirectory

from container_magic.core.config import ContainerMagicConfig
from container_magic.generators.dockerfile import generate_dockerfile


def _generate(config_dict):
    """Generate a Dockerfile from a config dict and return its content."""
    config = ContainerMagicConfig(**config_dict)
    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        generate_dockerfile(config, output_path)
        return output_path.read_text()


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


class TestVenvCreation:
    def test_pip_as_root_creates_venv(self):
        """First pip step as root injects venv setup."""
        config = _base_config(steps=[{"pip": {"install": ["numpy"]}}])
        content = _generate(config)
        assert "python3 -m venv --system-site-packages /opt/venv" in content
        assert "ENV VIRTUAL_ENV=/opt/venv" in content
        assert 'ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"' in content
        # Should NOT have USER switching (already root)
        lines = content.splitlines()
        venv_idx = next(
            i for i, line in enumerate(lines) if "venv" in line and "RUN" in line
        )
        # No USER root before venv line
        assert "USER root" not in lines[venv_idx - 1]

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
        # Find venv creation
        venv_idx = next(
            i for i, line in enumerate(lines) if "venv" in line and "RUN" in line
        )
        # USER root before venv creation
        preceding = [line.strip() for line in lines[:venv_idx] if line.strip()]
        assert preceding[-1] == "USER root"
        # USER restore after ENV PATH
        path_idx = next(
            i
            for i, line in enumerate(lines)
            if "VIRTUAL_ENV" in line and "PATH" in line
        )
        restore_lines = [line.strip() for line in lines[path_idx + 1 :] if line.strip()]
        assert restore_lines[0].startswith("USER ")
        assert restore_lines[0] != "USER root"

    def test_child_stage_inherits_venv(self):
        """Pip step in child stage skips venv setup if parent already created one."""
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
        assert content.count("python3 -m venv") == 1

    def test_child_stage_without_parent_venv_creates_own(self):
        """Pip step in child stage creates venv if parent had no pip steps."""
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
        assert "python3 -m venv" in content
        assert "USER root" in content

    def test_no_pip_steps_no_venv(self):
        """No venv setup when no pip steps exist."""
        config = _base_config(steps=[{"run": "echo hello"}])
        content = _generate(config)
        assert "venv" not in content
        assert "VIRTUAL_ENV" not in content

    def test_multiple_pip_steps_single_venv(self):
        """Multiple pip steps in same stage only create venv once."""
        config = _base_config(
            steps=[
                {"pip": {"install": ["numpy"]}},
                {"pip": {"install": ["flask"]}},
            ]
        )
        content = _generate(config)
        assert content.count("python3 -m venv") == 1
        assert content.count("ENV VIRTUAL_ENV=") == 1

    def test_venv_env_ordering(self):
        """VIRTUAL_ENV must be set before PATH references it."""
        config = _base_config(steps=[{"pip": {"install": ["numpy"]}}])
        content = _generate(config)
        lines = content.splitlines()
        venv_env_idx = next(
            i for i, line in enumerate(lines) if "VIRTUAL_ENV=/opt/venv" in line
        )
        path_env_idx = next(
            i for i, line in enumerate(lines) if "VIRTUAL_ENV}/bin" in line
        )
        assert venv_env_idx < path_env_idx

    def test_venv_guard_prevents_clobbering(self):
        """Venv creation uses test -f guard for idempotency."""
        config = _base_config(steps=[{"pip": {"install": ["numpy"]}}])
        content = _generate(config)
        assert "test -f /opt/venv/pyvenv.cfg" in content

    def test_pip_single_package_string(self):
        """Pip step with single package as string (not list) also creates venv."""
        config = _base_config(steps=[{"pip": {"install": "requests"}}])
        content = _generate(config)
        assert "python3 -m venv --system-site-packages /opt/venv" in content
        assert "requests" in content

    def test_become_without_create_user(self):
        """Pip after become to a pre-existing user (no create step) still switches to root."""
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
        assert "python3 -m venv" in content

    def test_venv_chowned_to_user_in_leaf_stage(self):
        """Venv is chowned to the configured user so it's writable at runtime."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "appuser"},
            "stages": {
                "base": {
                    "from": "debian:bookworm-slim",
                    "steps": [
                        {"pip": {"install": ["flask"]}},
                    ],
                },
                "development": {"from": "base"},
                "production": {"from": "base"},
            },
        }
        content = _generate(config)
        assert "chown -R" in content
        assert "/opt/venv" in content

    def test_venv_chown_not_added_for_root_user(self):
        """No venv chown when user is root."""
        config = _base_config(steps=[{"pip": {"install": ["numpy"]}}])
        content = _generate(config)
        assert (
            "chown" not in content
            or "USER_HOME" in content.split("chown")[0].split("\n")[-1]
        )

    def test_venv_chown_after_all_pip_steps(self):
        """Venv chown appears after the last pip install, not between them."""
        config = {
            "names": {"image": "test", "workspace": "workspace", "user": "appuser"},
            "stages": {
                "base": {
                    "from": "debian:bookworm-slim",
                    "steps": [
                        {"pip": {"install": ["flask"]}},
                        {"pip": {"install": ["numpy"]}},
                    ],
                },
                "development": {"from": "base"},
                "production": {"from": "base"},
            },
        }
        content = _generate(config)
        lines = content.splitlines()
        pip_lines = [i for i, line in enumerate(lines) if "pip install" in line]
        chown_lines = [
            i for i, line in enumerate(lines) if "chown" in line and "/opt/venv" in line
        ]
        assert len(chown_lines) >= 1
        assert chown_lines[0] > pip_lines[-1]

    def test_venv_chown_switches_to_root_when_base_has_become(self):
        """Venv chown wraps with USER root when inheriting non-root context."""
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
        chown_lines = [
            i for i, line in enumerate(lines) if "chown" in line and "/opt/venv" in line
        ]
        assert len(chown_lines) >= 1
        # USER root should appear before the chown
        chown_idx = chown_lines[0]
        preceding = [line.strip() for line in lines[:chown_idx] if line.strip()]
        assert preceding[-1] == "USER root"

    def test_stage_from_external_image_resets_venv(self):
        """Stage from external image (not parent stage) starts fresh."""
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
        assert content.count("python3 -m venv") == 2
