"""Packaging guards: runtime data files must be shipped in the built wheel.

These resources load by filesystem path from inside the installed package, so
they are only present in a wheel if a ``[tool.setuptools.package-data]`` glob
covers them. Editable/source installs always have them, which is how the
missing ``registry/*.yaml`` glob went unnoticed until a clean wheel install.
"""

from fnmatch import fnmatch
from pathlib import Path

import pytest

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - exercised on <3.11 only
    try:
        import tomli as tomllib
    except ModuleNotFoundError:  # pragma: no cover
        tomllib = None

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PKG = _REPO_ROOT / "src" / "container_magic"


def _package_data_globs():
    data = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text())
    return data["tool"]["setuptools"]["package-data"]["container_magic"]


@pytest.mark.skipif(tomllib is None, reason="no TOML parser available")
def test_registry_yaml_files_are_in_package_data():
    """Built-in registry YAML files load via filesystem path and must ship.

    Regression: they were absent from package-data, so a clean wheel/PyPI
    install had an empty registry and every apt-get/pip/apk/dnf step broke.
    """
    yamls = sorted((_PKG / "registry").glob("*.yaml"))
    assert yamls, "expected built-in registry YAML files under registry/"

    globs = _package_data_globs()
    for yaml in yamls:
        rel = f"registry/{yaml.name}"
        assert any(fnmatch(rel, g) for g in globs), (
            f"{rel} is not covered by package-data {globs}; "
            "a wheel install would ship an empty registry"
        )
