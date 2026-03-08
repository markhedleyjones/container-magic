"""Tests for the assets manifest system."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from container_magic.core.cache import build_asset_map
from container_magic.core.config import (
    AssetItem,
    ContainerMagicConfig,
    _parse_asset_items,
)
from container_magic.generators.dockerfile import (
    _resolve_copy_source,
    generate_dockerfile,
)


def _generate(config_dict):
    """Generate a Dockerfile from a config dict and return its content."""
    config = ContainerMagicConfig(**config_dict)
    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Dockerfile"
        generate_dockerfile(config, output_path)
        return output_path.read_text()


def _base_config(**overrides):
    """Minimal valid config with overrides applied at root level."""
    config = {
        "names": {"project": "test", "workspace": "workspace", "user": "root"},
        "stages": {
            "base": {"from": "python:3-slim", "steps": []},
            "development": {"from": "base", "steps": []},
            "production": {"from": "base", "steps": []},
        },
    }
    config.update(overrides)
    return config


class TestParseAssetItems:
    def test_bare_url(self):
        items = _parse_asset_items(["https://example.com/model.bin"])
        assert len(items) == 1
        assert items[0].filename == "model.bin"
        assert items[0].url == "https://example.com/model.bin"

    def test_named_asset(self):
        items = _parse_asset_items(
            [{"weights.bin": "https://example.com/download?file=model&v=2"}]
        )
        assert len(items) == 1
        assert items[0].filename == "weights.bin"
        assert items[0].url == "https://example.com/download?file=model&v=2"

    def test_mixed_assets(self):
        items = _parse_asset_items(
            [
                "https://example.com/cuda-keyring_1.1-1_all.deb",
                {"model.bin": "https://example.com/download?file=model&v=2"},
            ]
        )
        assert len(items) == 2
        assert items[0].filename == "cuda-keyring_1.1-1_all.deb"
        assert items[1].filename == "model.bin"

    def test_empty_list(self):
        items = _parse_asset_items([])
        assert items == []

    def test_invalid_url_scheme(self):
        with pytest.raises(ValueError, match="http:// or https://"):
            _parse_asset_items(["ftp://example.com/file.bin"])

    def test_duplicate_filename(self):
        with pytest.raises(ValueError, match="duplicate filename"):
            _parse_asset_items(
                [
                    "https://example.com/file.bin",
                    "https://other.com/file.bin",
                ]
            )

    def test_unresolvable_filename(self):
        with pytest.raises(ValueError, match="cannot derive filename"):
            _parse_asset_items(["https://example.com/"])

    def test_named_asset_empty_filename(self):
        with pytest.raises(ValueError, match="filename must not be empty"):
            _parse_asset_items([{"": "https://example.com/file.bin"}])

    def test_named_asset_invalid_url(self):
        with pytest.raises(ValueError, match="http:// or https://"):
            _parse_asset_items([{"file.bin": "not-a-url"}])

    def test_named_asset_multiple_keys(self):
        with pytest.raises(ValueError, match="single-key dict"):
            _parse_asset_items(
                [{"a.bin": "https://x.com/a", "b.bin": "https://x.com/b"}]
            )

    def test_invalid_entry_type(self):
        with pytest.raises(ValueError, match="URL string or a"):
            _parse_asset_items([42])

    def test_http_url_accepted(self):
        items = _parse_asset_items(["http://example.com/file.bin"])
        assert items[0].url == "http://example.com/file.bin"


class TestConfigAssets:
    def test_config_with_assets(self):
        config = ContainerMagicConfig(
            names={"project": "test", "user": "root"},
            assets=["https://example.com/model.bin"],
            stages={
                "base": {"from": "python:3-slim", "steps": []},
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
            },
        )
        assert len(config.assets) == 1
        assert config.assets[0].filename == "model.bin"

    def test_config_without_assets(self):
        config = ContainerMagicConfig(
            names={"project": "test", "user": "root"},
            stages={
                "base": {"from": "python:3-slim", "steps": []},
                "development": {"from": "base", "steps": []},
                "production": {"from": "base", "steps": []},
            },
        )
        assert config.assets == []


class TestBuildAssetMap:
    def test_builds_map(self):
        assets = [
            AssetItem(filename="model.bin", url="https://example.com/model.bin"),
            AssetItem(filename="data.csv", url="https://example.com/data.csv"),
        ]
        with TemporaryDirectory() as tmpdir:
            asset_map = build_asset_map(Path(tmpdir), assets)
            assert "model.bin" in asset_map
            assert "data.csv" in asset_map
            assert asset_map["model.bin"].startswith(".cm-cache/assets/")
            assert asset_map["model.bin"].endswith("/model.bin")

    def test_empty_assets(self):
        with TemporaryDirectory() as tmpdir:
            asset_map = build_asset_map(Path(tmpdir), [])
            assert asset_map == {}


class TestResolveCopySource:
    def test_asset_match_rewrites(self):
        asset_map = {"model.bin": ".cm-cache/assets/abc123/model.bin"}
        result = _resolve_copy_source("model.bin /models/model.bin", asset_map)
        assert result == ".cm-cache/assets/abc123/model.bin /models/model.bin"

    def test_no_match_unchanged(self):
        asset_map = {"model.bin": ".cm-cache/assets/abc123/model.bin"}
        result = _resolve_copy_source("local-file.txt /dest/", asset_map)
        assert result == "local-file.txt /dest/"

    def test_empty_map(self):
        result = _resolve_copy_source("file.txt /dest/", {})
        assert result == "file.txt /dest/"

    def test_empty_args(self):
        result = _resolve_copy_source("", {"a": "b"})
        assert result == ""


class TestDockerfileAssetCopyResolution:
    def test_copy_step_resolves_asset(self):
        config = _base_config(
            assets=["https://example.com/cuda-keyring_1.1-1_all.deb"],
        )
        config["stages"]["base"]["steps"] = [
            {"copy": "cuda-keyring_1.1-1_all.deb /tmp/cuda-keyring.deb"},
        ]
        content = _generate(config)
        assert ".cm-cache/assets/" in content
        assert "/tmp/cuda-keyring.deb" in content

    def test_copy_step_non_asset_unchanged(self):
        config = _base_config(
            assets=["https://example.com/model.bin"],
        )
        config["stages"]["base"]["steps"] = [
            {"copy": "local-config.txt /etc/config"},
        ]
        content = _generate(config)
        assert "COPY local-config.txt /etc/config" in content
        assert ".cm-cache" not in content.split("local-config.txt")[0].split("\n")[-1]


class TestAssetFixtureConfig:
    def test_new_syntax_fixture_loads(self):
        fixture_path = (
            Path(__file__).parent.parent / "fixtures" / "configs" / "with_assets.yaml"
        )
        if fixture_path.exists():
            config = ContainerMagicConfig.from_yaml(fixture_path)
            assert len(config.assets) > 0
