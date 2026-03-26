"""Tests for configuration schema and validation."""

import pytest
from pydantic import ValidationError

from container_magic.core.config import ContainerMagicConfig, RuntimeConfig


def test_valid_image_name():
    """Test that valid image names are accepted."""
    valid_names = ["my-project", "my_project", "myproject", "my-project-123"]
    for name in valid_names:
        config = ContainerMagicConfig(
            names={"image": name, "workspace": "workspace", "user": "root"},
            stages={
                "base": {"from": "debian:bookworm-slim"},
                "development": {"from": "base"},
                "production": {"from": "base"},
            },
        )
        assert config.names.image == name


def test_invalid_image_name():
    """Test that invalid image names are rejected."""
    invalid_names = ["my project", "my/project", "my.project", "my@project"]
    for name in invalid_names:
        with pytest.raises(ValidationError):
            ContainerMagicConfig(
                names={"image": name, "workspace": "workspace", "user": "root"},
                stages={
                    "base": {"from": "debian:bookworm-slim"},
                    "development": {"from": "base"},
                    "production": {"from": "base"},
                },
            )


def test_default_values():
    """Test that default values are set correctly."""
    config = ContainerMagicConfig(
        names={"image": "test", "user": "root"},
        stages={
            "base": {"from": "debian:bookworm-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
    )

    assert config.names.workspace == "workspace"
    assert config.names.user == "root"
    assert config.backend == "auto"
    assert config.runtime.privileged is False
    assert config.runtime.features == []
    assert config.runtime.volumes == []
    assert config.runtime.devices == []
    assert config.runtime.network_mode is None


def test_names_user_required():
    """Test that names.user must be provided."""
    with pytest.raises(ValidationError, match="user"):
        ContainerMagicConfig(
            names={"image": "test"},
            stages={
                "base": {"from": "debian:bookworm-slim"},
                "development": {"from": "base"},
                "production": {"from": "base"},
            },
        )


def test_config_with_features():
    """Test configuration with features enabled."""
    config = ContainerMagicConfig(
        names={"image": "test", "user": "root"},
        runtime={"features": ["display", "gpu", "audio"]},
        stages={
            "base": {"from": "debian:bookworm-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
    )

    assert config.runtime.features == ["display", "gpu", "audio"]


def test_config_with_volumes():
    """Test configuration with volumes."""
    config = ContainerMagicConfig(
        names={"image": "test", "user": "root"},
        runtime={"volumes": ["/tmp/data:/data:ro", "/var/log:/logs"]},
        stages={
            "base": {"from": "debian:bookworm-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
    )

    assert config.runtime.volumes == ["/tmp/data:/data:ro", "/var/log:/logs"]


def test_config_with_devices():
    """Test configuration with devices."""
    config = ContainerMagicConfig(
        names={"image": "test", "user": "root"},
        runtime={"devices": ["/dev/ttyUSB0", "/dev/video0:/dev/video0:rw"]},
        stages={
            "base": {"from": "debian:bookworm-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
        },
    )

    assert config.runtime.devices == ["/dev/ttyUSB0", "/dev/video0:/dev/video0:rw"]


def test_invalid_volume_format():
    """Test that invalid volume strings are rejected."""
    with pytest.raises(ValidationError, match="Invalid volume format"):
        ContainerMagicConfig(
            names={"image": "test", "user": "root"},
            runtime={"volumes": ["no-colon"]},
            stages={
                "base": {"from": "debian:bookworm-slim"},
                "development": {"from": "base"},
                "production": {"from": "base"},
            },
        )


def test_invalid_volume_empty_parts():
    """Test that volume strings with empty host or container are rejected."""
    with pytest.raises(ValidationError, match="Invalid volume format"):
        ContainerMagicConfig(
            names={"image": "test", "user": "root"},
            runtime={"volumes": [":/container"]},
            stages={
                "base": {"from": "debian:bookworm-slim"},
                "development": {"from": "base"},
                "production": {"from": "base"},
            },
        )


def test_removed_runtime_backend_raises():
    """Test that runtime.backend is rejected with a migration message."""
    with pytest.raises(ValidationError, match="root-level"):
        ContainerMagicConfig(
            names={"image": "test", "user": "root"},
            runtime={"backend": "docker"},
            stages={
                "base": {"from": "debian:bookworm-slim"},
                "development": {"from": "base"},
                "production": {"from": "base"},
            },
        )


def test_removed_network_field_raises():
    """Test that runtime.network is rejected with a migration message."""
    with pytest.raises(ValidationError, match="network_mode"):
        ContainerMagicConfig(
            names={"image": "test", "user": "root"},
            runtime={"network": "host"},
            stages={
                "base": {"from": "debian:bookworm-slim"},
                "development": {"from": "base"},
                "production": {"from": "base"},
            },
        )


def test_build_script_custom_default_target():
    """Test that build_script.default_target can be customised."""
    config = ContainerMagicConfig(
        names={"image": "test", "user": "root"},
        stages={
            "base": {"from": "debian:bookworm-slim"},
            "development": {"from": "base"},
            "production": {"from": "base"},
            "testing": {"from": "base"},
        },
        build_script={"default_target": "testing"},
    )

    assert config.build_script.default_target == "testing"


def test_build_script_invalid_default_target():
    """Test that build_script.default_target must exist in stages."""
    with pytest.raises(ValidationError) as exc_info:
        ContainerMagicConfig(
            names={"image": "test", "user": "root"},
            stages={
                "base": {"from": "debian:bookworm-slim"},
                "development": {"from": "base"},
                "production": {"from": "base"},
            },
            build_script={"default_target": "nonexistent"},
        )

    assert "does not exist in stages" in str(exc_info.value)


def test_user_block_rejected():
    """Test that user: config block raises a migration error."""
    with pytest.raises(ValidationError, match="no longer supported"):
        ContainerMagicConfig(
            names={"image": "test", "user": "root"},
            user={"name": "appuser"},
            stages={
                "base": {"from": "debian:bookworm-slim"},
                "development": {"from": "base"},
                "production": {"from": "base"},
            },
        )


def test_auto_update_rejected():
    """Test that auto_update raises a clean removal error."""
    with pytest.raises(ValidationError, match="no longer used"):
        ContainerMagicConfig(
            names={"image": "test", "user": "root"},
            auto_update=True,
            stages={
                "base": {"from": "debian:bookworm-slim"},
                "development": {"from": "base"},
                "production": {"from": "base"},
            },
        )


def test_project_block_rejected():
    """Test that project: config block raises a migration error."""
    with pytest.raises(ValidationError, match="replaced by 'names'"):
        ContainerMagicConfig(
            project={"name": "test"},
            stages={
                "base": {"from": "debian:bookworm-slim"},
                "development": {"from": "base"},
                "production": {"from": "base"},
            },
        )


def test_create_user_rejected_when_user_is_root():
    """Test that create: user with names.user='root' raises an error."""
    with pytest.raises(ValidationError, match="root always exists"):
        ContainerMagicConfig(
            names={"image": "test", "user": "root"},
            stages={
                "base": {"from": "debian:bookworm-slim", "steps": [{"create": "user"}]},
                "development": {"from": "base"},
                "production": {"from": "base"},
            },
        )


def test_become_user_rejected_when_user_is_root():
    """Test that become: user with names.user='root' raises an error."""
    with pytest.raises(ValidationError, match="redundant"):
        ContainerMagicConfig(
            names={"image": "test", "user": "root"},
            stages={
                "base": {"from": "debian:bookworm-slim"},
                "development": {"from": "base", "steps": [{"become": "user"}]},
                "production": {"from": "base"},
            },
        )


def test_become_literal_with_root_user():
    """Test that become: www-data works when names.user is 'root'."""
    config = ContainerMagicConfig(
        names={"image": "test", "user": "root"},
        stages={
            "base": {"from": "debian:bookworm-slim"},
            "development": {"from": "base", "steps": [{"become": "www-data"}]},
            "production": {"from": "base"},
        },
    )
    assert config.names.user == "root"


def test_copy_non_workspace_without_workspace_warns(capsys):
    """Test that copying a non-workspace directory without workspace copy warns."""
    ContainerMagicConfig(
        names={"image": "test", "user": "root", "workspace": "workspace"},
        stages={
            "base": {"from": "debian:bookworm-slim"},
            "development": {"from": "base"},
            "production": {"from": "base", "steps": [{"copy": "app"}]},
        },
    )
    captured = capsys.readouterr()
    assert "Warning" in captured.err
    assert "app" in captured.err
    assert "workspace" in captured.err


def test_copy_non_workspace_with_workspace_infos(capsys):
    """Test that copying a non-workspace directory alongside workspace emits info."""
    ContainerMagicConfig(
        names={"image": "test", "user": "root", "workspace": "workspace"},
        stages={
            "base": {"from": "debian:bookworm-slim"},
            "development": {"from": "base"},
            "production": {
                "from": "base",
                "steps": [{"copy": "workspace"}, {"copy": "extras"}],
            },
        },
    )
    captured = capsys.readouterr()
    assert "Info" in captured.err
    assert "extras" in captured.err


def test_copy_workspace_no_warning(capsys):
    """Test that copying only the workspace directory produces no warning."""
    ContainerMagicConfig(
        names={"image": "test", "user": "root", "workspace": "workspace"},
        stages={
            "base": {"from": "debian:bookworm-slim"},
            "development": {"from": "base"},
            "production": {"from": "base", "steps": [{"copy": "workspace"}]},
        },
    )
    captured = capsys.readouterr()
    assert "Warning" not in captured.err
    assert "Info" not in captured.err


def test_copy_with_dest_no_warning(capsys):
    """Test that multi-token copy (source dest) does not trigger workspace warnings."""
    ContainerMagicConfig(
        names={"image": "test", "user": "root", "workspace": "workspace"},
        stages={
            "base": {"from": "debian:bookworm-slim"},
            "development": {"from": "base"},
            "production": {
                "from": "base",
                "steps": [{"copy": "config.yaml /etc/config.yaml"}],
            },
        },
    )
    captured = capsys.readouterr()
    assert "Warning" not in captured.err
    assert "Info" not in captured.err


def test_stage_shell_rejected_with_migration_message():
    """Stage-level shell field should be rejected pointing to runtime.shell."""
    with pytest.raises(ValidationError, match="runtime.shell"):
        ContainerMagicConfig(
            names={"image": "test", "user": "root"},
            stages={
                "base": {"from": "debian:bookworm-slim", "shell": "/bin/bash"},
                "development": {"from": "base"},
                "production": {"from": "base"},
            },
        )


class TestRuntimeMerge:
    def test_scalar_override(self):
        global_rt = RuntimeConfig(network_mode="bridge", ipc="private")
        stage_rt = RuntimeConfig(network_mode="host")
        merged = global_rt.merge_with(stage_rt)
        assert merged.network_mode == "host"
        assert merged.ipc == "private"

    def test_list_append_volumes(self):
        global_rt = RuntimeConfig(volumes=["/data:/data"])
        stage_rt = RuntimeConfig(volumes=["~/.config:~/.config"])
        merged = global_rt.merge_with(stage_rt)
        assert merged.volumes == ["/data:/data", "~/.config:~/.config"]

    def test_list_append_features(self):
        global_rt = RuntimeConfig(features=["gpu"])
        stage_rt = RuntimeConfig(features=["display"])
        merged = global_rt.merge_with(stage_rt)
        assert "gpu" in merged.features
        assert "display" in merged.features

    def test_features_deduplicated(self):
        global_rt = RuntimeConfig(features=["gpu"])
        stage_rt = RuntimeConfig(features=["gpu", "display"])
        merged = global_rt.merge_with(stage_rt)
        assert merged.features.count("gpu") == 1

    def test_list_append_devices(self):
        global_rt = RuntimeConfig(devices=["/dev/video0:/dev/video0"])
        stage_rt = RuntimeConfig(devices=["/dev/dri:/dev/dri"])
        merged = global_rt.merge_with(stage_rt)
        assert len(merged.devices) == 2

    def test_empty_stage_returns_global(self):
        global_rt = RuntimeConfig(network_mode="host", volumes=["/data:/data"])
        stage_rt = RuntimeConfig()
        merged = global_rt.merge_with(stage_rt)
        assert merged.network_mode == "host"
        assert merged.volumes == ["/data:/data"]

    def test_shell_override(self):
        global_rt = RuntimeConfig(shell="/bin/bash")
        stage_rt = RuntimeConfig(shell="/bin/sh")
        merged = global_rt.merge_with(stage_rt)
        assert merged.shell == "/bin/sh"

    def test_privileged_override(self):
        global_rt = RuntimeConfig(privileged=False)
        stage_rt = RuntimeConfig(privileged=True)
        merged = global_rt.merge_with(stage_rt)
        assert merged.privileged is True


class TestEffectiveRuntime:
    def _make_config(self, **overrides):
        data = {
            "names": {"image": "test", "user": "root"},
            "stages": {
                "base": {"from": "debian:bookworm-slim"},
                "development": {"from": "base"},
                "production": {"from": "base"},
            },
        }
        data.update(overrides)
        return ContainerMagicConfig(**data)

    def test_no_stage_runtime_returns_global(self):
        config = self._make_config(runtime={"network_mode": "host"})
        rt = config.effective_runtime("development")
        assert rt.network_mode == "host"

    def test_stage_runtime_merges_with_global(self):
        config = self._make_config(
            runtime={"volumes": ["/data:/data"]},
            stages={
                "base": {"from": "debian:bookworm-slim"},
                "development": {
                    "from": "base",
                    "runtime": {"volumes": ["~/.config:~/.config"]},
                },
                "production": {"from": "base"},
            },
        )
        dev_rt = config.effective_runtime("development")
        assert len(dev_rt.volumes) == 2
        prod_rt = config.effective_runtime("production")
        assert len(prod_rt.volumes) == 1

    def test_stage_scalar_overrides_global(self):
        config = self._make_config(
            runtime={"network_mode": "bridge"},
            stages={
                "base": {"from": "debian:bookworm-slim"},
                "development": {
                    "from": "base",
                    "runtime": {"network_mode": "host"},
                },
                "production": {"from": "base"},
            },
        )
        dev_rt = config.effective_runtime("development")
        assert dev_rt.network_mode == "host"
        prod_rt = config.effective_runtime("production")
        assert prod_rt.network_mode == "bridge"
