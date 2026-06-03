"""Tests for build-time secrets (BuildKit --mount=type=secret)."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from pydantic import ValidationError

from container_magic.core.config import ContainerMagicConfig
from container_magic.generators.build_script import generate_build_script


def _config(**extra):
    return {
        "names": {"image": "test", "user": "app"},
        "stages": {
            "base": {"from": "debian:bookworm-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
        **extra,
    }


def _build_sh(config_dict):
    config = ContainerMagicConfig(**config_dict)
    with TemporaryDirectory() as tmp:
        project_dir = Path(tmp)
        generate_build_script(config, project_dir)
        return (project_dir / "build.sh").read_text()


def test_build_secret_with_src_emits_secret_flag():
    content = _build_sh(
        _config(build_secrets=[{"id": "aws", "src": "~/.aws/credentials"}])
    )
    # ~ is rewritten to ${HOME} so the committed script stays portable.
    assert "--secret id=aws,src=${HOME}/.aws/credentials" in content


def test_build_secret_with_env_emits_secret_flag():
    content = _build_sh(_config(build_secrets=[{"id": "tok", "env": "PIP_TOKEN"}]))
    assert "--secret id=tok,env=PIP_TOKEN" in content


def test_build_secret_absolute_src_unchanged():
    content = _build_sh(_config(build_secrets=[{"id": "key", "src": "/run/keys/key"}]))
    assert "--secret id=key,src=/run/keys/key" in content


def test_no_build_secrets_emits_no_secret_flag():
    content = _build_sh(_config())
    assert "--secret" not in content


def test_generated_build_sh_is_valid_bash_with_and_without_secrets():
    import shutil
    import subprocess

    bash = shutil.which("bash")
    if bash is None:  # pragma: no cover
        pytest.skip("bash not available")
    for secrets in ([], [{"id": "aws", "src": "~/.aws/credentials"}]):
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            config = ContainerMagicConfig(**_config(build_secrets=secrets))
            generate_build_script(config, project_dir)
            script = project_dir / "build.sh"
            result = subprocess.run(
                [bash, "-n", str(script)], capture_output=True, text=True
            )
            assert result.returncode == 0, result.stderr


def test_build_secret_requires_a_source():
    with pytest.raises(ValidationError, match="exactly one of"):
        ContainerMagicConfig(**_config(build_secrets=[{"id": "aws"}]))


def test_build_secret_rejects_two_sources():
    with pytest.raises(ValidationError, match="exactly one of"):
        ContainerMagicConfig(
            **_config(build_secrets=[{"id": "aws", "src": "/x", "env": "Y"}])
        )
