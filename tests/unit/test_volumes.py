"""Unit tests for volume SELinux labelling and variable expansion."""

import pytest

from container_magic.core.volumes import (
    VolumeContext,
    container_path_of,
    ensure_selinux_label,
    expand_mount_path,
    expand_volume,
    expand_volumes_for_run,
    expand_volumes_for_script,
    is_shorthand_volume,
    label_volumes,
    parse_shorthand,
    shorthand_anchored_paths,
    validate_shorthand_basename,
)


class TestEnsureSelinuxLabel:
    def test_no_options(self):
        assert ensure_selinux_label("/host:/container") == "/host:/container:z"

    def test_ro_option(self):
        assert ensure_selinux_label("/host:/container:ro") == "/host:/container:ro,z"

    def test_rw_option(self):
        assert ensure_selinux_label("/host:/container:rw") == "/host:/container:rw,z"

    def test_already_has_z(self):
        assert ensure_selinux_label("/host:/container:z") == "/host:/container:z"

    def test_already_has_ro_z(self):
        assert ensure_selinux_label("/host:/container:ro,z") == "/host:/container:ro,z"

    def test_already_has_uppercase_z(self):
        assert ensure_selinux_label("/host:/container:Z") == "/host:/container:Z"

    def test_already_has_ro_uppercase_z(self):
        assert ensure_selinux_label("/host:/container:ro,Z") == "/host:/container:ro,Z"

    def test_single_part_unchanged(self):
        assert ensure_selinux_label("named-volume") == "named-volume"

    def test_z_in_middle_of_options(self):
        assert ensure_selinux_label("/host:/container:z,ro") == "/host:/container:z,ro"

    def test_complex_path_with_colons(self):
        result = ensure_selinux_label("/host/path:/container/path:ro")
        assert result == "/host/path:/container/path:ro,z"

    def test_named_volume(self):
        assert (
            ensure_selinux_label("myvolume:/container/path")
            == "myvolume:/container/path:z"
        )

    def test_compound_options_with_nocopy(self):
        assert (
            ensure_selinux_label("/host:/container:ro,nocopy")
            == "/host:/container:ro,nocopy,z"
        )


class TestLabelVolumes:
    def test_empty_list(self):
        assert label_volumes([]) == []

    def test_mixed_volumes(self):
        result = label_volumes(
            [
                "/tmp/data:/data:ro",
                "/var/log:/logs",
                "/host:/container:z",
            ]
        )
        assert result == [
            "/tmp/data:/data:ro,z",
            "/var/log:/logs:z",
            "/host:/container:z",
        ]


def _make_context(**overrides):
    defaults = dict(
        user_home="/home/mark",
        container_home="/home/appuser",
        workspace_user="/home/mark/repos/myproject/workspace",
        workspace_container="/home/appuser/workspace",
        project_dir="/home/mark/repos/myproject",
    )
    defaults.update(overrides)
    return VolumeContext(**defaults)


class TestExpandVolume:
    def test_tilde_both_sides(self):
        ctx = _make_context()
        result = expand_volume("~/.config/tool:~/.config/tool", ctx)
        assert result == "/home/mark/.config/tool:/home/appuser/.config/tool"

    def test_tilde_user_side_only(self):
        ctx = _make_context()
        result = expand_volume("~/data:/mnt/data:ro", ctx)
        assert result == "/home/mark/data:/mnt/data:ro"

    def test_dollar_home_both_sides(self):
        ctx = _make_context()
        result = expand_volume("$HOME/.ssh:$HOME/.ssh:ro", ctx)
        assert result == "/home/mark/.ssh:/home/appuser/.ssh:ro"

    def test_workspace_both_sides(self):
        ctx = _make_context()
        result = expand_volume("$WORKSPACE/output:$WORKSPACE/output", ctx)
        assert result == (
            "/home/mark/repos/myproject/workspace/output:/home/appuser/workspace/output"
        )

    def test_no_variables_unchanged(self):
        ctx = _make_context()
        result = expand_volume("/tmp/data:/data:ro", ctx)
        assert result == "/tmp/data:/data:ro"

    def test_options_preserved(self):
        ctx = _make_context()
        result = expand_volume("~/.config:~/.config:ro,z", ctx)
        assert result == "/home/mark/.config:/home/appuser/.config:ro,z"

    def test_tilde_mid_path_not_expanded(self):
        ctx = _make_context()
        result = expand_volume("/tmp/~test:/data/~test", ctx)
        assert result == "/tmp/~test:/data/~test"

    def test_dollar_home_mid_path_not_expanded(self):
        ctx = _make_context()
        result = expand_volume("/tmp/$HOME:/data/$HOME", ctx)
        assert result == "/tmp/$HOME:/data/$HOME"

    def test_root_container_home(self):
        ctx = _make_context(container_home="/root")
        result = expand_volume("~/.config:~/.config", ctx)
        assert result == "/home/mark/.config:/root/.config"

    def test_shorthand_expands_with_project_dir(self):
        ctx = _make_context()
        result = expand_volume("outputs", ctx)
        assert result == "/home/mark/repos/myproject/outputs:/data/outputs"

    def test_shorthand_expands_without_project_dir(self):
        ctx = _make_context(project_dir=None)
        result = expand_volume("outputs", ctx)
        assert result == "./outputs:/data/outputs"

    def test_shorthand_relative_path_basename(self):
        ctx = _make_context()
        result = expand_volume("outputs/sub", ctx)
        assert result == "/home/mark/repos/myproject/outputs/sub:/data/sub"

    def test_tilde_alone(self):
        ctx = _make_context()
        result = expand_volume("~:~", ctx)
        assert result == "/home/mark:/home/appuser"

    def test_dollar_home_alone(self):
        ctx = _make_context()
        result = expand_volume("$HOME:$HOME", ctx)
        assert result == "/home/mark:/home/appuser"


class TestExpandVolumesForRun:
    def test_expands_all_variables(self):
        ctx = _make_context()
        volumes = [
            "~/.config/tool:~/.config/tool",
            "$WORKSPACE/data:$WORKSPACE/data:ro",
            "/absolute:/absolute",
        ]
        result = expand_volumes_for_run(volumes, ctx)
        assert result == [
            "/home/mark/.config/tool:/home/appuser/.config/tool",
            "/home/mark/repos/myproject/workspace/data:/home/appuser/workspace/data:ro",
            "/absolute:/absolute",
        ]

    def test_empty_list(self):
        ctx = _make_context()
        assert expand_volumes_for_run([], ctx) == []


class TestExpandVolumesForScript:
    def test_tilde_rendered_as_shell_variable(self):
        result = expand_volumes_for_script(
            ["~/.config/tool:~/.config/tool"],
            container_home="/home/appuser",
        )
        assert result == ["$HOME/.config/tool:/home/appuser/.config/tool"]

    def test_dollar_home_rendered_as_shell_variable(self):
        result = expand_volumes_for_script(
            ["$HOME/.config:$HOME/.config:ro"],
            container_home="/home/appuser",
        )
        assert result == ["$HOME/.config:/home/appuser/.config:ro"]

    def test_workspace_volumes_filtered_out(self, capsys):
        result = expand_volumes_for_script(
            [
                "~/.config:~/.config",
                "$WORKSPACE/output:$WORKSPACE/output",
                "$HOME/data:/data",
            ],
            container_home="/home/appuser",
        )
        assert len(result) == 2
        assert result[0] == "$HOME/.config:/home/appuser/.config"
        assert result[1] == "$HOME/data:/data"
        captured = capsys.readouterr()
        assert "$WORKSPACE" in captured.err
        assert "cm run" in captured.err

    def test_workspace_on_container_side_only_filtered(self, capsys):
        result = expand_volumes_for_script(
            ["/data:$WORKSPACE/data"],
            container_home="/home/appuser",
        )
        assert result == []
        captured = capsys.readouterr()
        assert "$WORKSPACE" in captured.err

    def test_workspace_mid_path_filtered(self, capsys):
        result = expand_volumes_for_script(
            ["/data/$WORKSPACE/output:/container/path"],
            container_home="/home/appuser",
        )
        assert result == []
        captured = capsys.readouterr()
        assert "$WORKSPACE" in captured.err

    def test_no_variables_unchanged(self):
        result = expand_volumes_for_script(
            ["/tmp/data:/data:ro"],
            container_home="/home/appuser",
        )
        assert result == ["/tmp/data:/data:ro"]

    def test_root_container_home(self):
        result = expand_volumes_for_script(
            ["~/.config:~/.config"],
            container_home="/root",
        )
        assert result == ["$HOME/.config:/root/.config"]

    def test_empty_list(self):
        result = expand_volumes_for_script([], container_home="/home/appuser")
        assert result == []


class TestShorthandHelpers:
    def test_is_shorthand_volume_bare_name(self):
        assert is_shorthand_volume("outputs") is True

    def test_is_shorthand_volume_with_colon(self):
        assert is_shorthand_volume("/host:/container") is False

    def test_validate_basename_accepts_alnum(self):
        validate_shorthand_basename("outputs")
        validate_shorthand_basename("cache_2")
        validate_shorthand_basename("my-data-1")

    def test_validate_basename_rejects_slash(self):
        with pytest.raises(ValueError, match="must match"):
            validate_shorthand_basename("outputs/sub")

    def test_validate_basename_rejects_empty(self):
        with pytest.raises(ValueError, match="must match"):
            validate_shorthand_basename("")

    def test_validate_basename_rejects_dotted(self):
        with pytest.raises(ValueError, match="must match"):
            validate_shorthand_basename("..")

    def test_parse_shorthand_bare(self):
        assert parse_shorthand("outputs") == ("outputs", "outputs")

    def test_parse_shorthand_relative(self):
        assert parse_shorthand("../shared") == ("../shared", "shared")

    def test_parse_shorthand_absolute(self):
        assert parse_shorthand("/srv/pipeline/outputs") == (
            "/srv/pipeline/outputs",
            "outputs",
        )

    def test_parse_shorthand_home_prefixed(self):
        assert parse_shorthand("~/datasets") == ("~/datasets", "datasets")

    def test_parse_shorthand_strips_trailing_slash(self):
        assert parse_shorthand("../shared/") == ("../shared", "shared")

    def test_parse_shorthand_rejects_empty(self):
        with pytest.raises(ValueError, match="empty"):
            parse_shorthand("")

    def test_parse_shorthand_rejects_dotdot_basename(self):
        with pytest.raises(ValueError, match="must match"):
            parse_shorthand("../..")

    def test_anchored_paths_filters_to_relative(self):
        result = shorthand_anchored_paths(
            [
                "outputs",
                "../shared",
                "/srv/data",
                "~/datasets",
                "$HOME/cache",
                "/tmp/x:/x",
            ]
        )
        assert result == ["outputs", "../shared"]

    def test_container_path_of_shorthand(self):
        assert container_path_of("outputs") == "/data/outputs"
        assert container_path_of("../shared") == "/data/shared"
        assert container_path_of("/srv/out") == "/data/out"

    def test_container_path_of_full_form(self):
        assert container_path_of("/host:/mnt/data:ro") == "/mnt/data"


class TestExpandShorthandForRun:
    def test_shorthand_expansion_absolute(self):
        ctx = _make_context()
        result = expand_volumes_for_run(["outputs"], ctx)
        assert result == ["/home/mark/repos/myproject/outputs:/data/outputs"]

    def test_mixed_shorthand_and_full(self):
        ctx = _make_context()
        result = expand_volumes_for_run(["outputs", "/tmp/data:/data:ro"], ctx)
        assert result == [
            "/home/mark/repos/myproject/outputs:/data/outputs",
            "/tmp/data:/data:ro",
        ]

    def test_shorthand_parent_dir_normalized(self):
        ctx = _make_context()
        result = expand_volumes_for_run(["../shared"], ctx)
        assert result == ["/home/mark/repos/shared:/data/shared"]

    def test_shorthand_absolute_host(self):
        ctx = _make_context()
        result = expand_volumes_for_run(["/srv/pipeline/outputs"], ctx)
        assert result == ["/srv/pipeline/outputs:/data/outputs"]

    def test_shorthand_home_expanded(self):
        ctx = _make_context()
        result = expand_volumes_for_run(["~/datasets"], ctx)
        assert result == ["/home/mark/datasets:/data/datasets"]

    def test_shorthand_trailing_slash_stripped(self):
        ctx = _make_context()
        result = expand_volumes_for_run(["../shared/"], ctx)
        assert result == ["/home/mark/repos/shared:/data/shared"]


class TestExpandShorthandForScript:
    def test_shorthand_uses_run_sh_dir(self):
        result = expand_volumes_for_script(["outputs"], container_home="/home/appuser")
        assert result == ["${_RUN_SH_DIR}/outputs:/data/outputs"]

    def test_mixed_shorthand_and_full(self):
        result = expand_volumes_for_script(
            ["outputs", "~/.config:~/.config"],
            container_home="/home/appuser",
        )
        assert result == [
            "${_RUN_SH_DIR}/outputs:/data/outputs",
            "$HOME/.config:/home/appuser/.config",
        ]

    def test_shorthand_parent_dir_relative_to_run_sh(self):
        result = expand_volumes_for_script(
            ["../shared"], container_home="/home/appuser"
        )
        assert result == ["${_RUN_SH_DIR}/../shared:/data/shared"]

    def test_shorthand_absolute_host_passthrough(self):
        result = expand_volumes_for_script(
            ["/srv/pipeline/outputs"], container_home="/home/appuser"
        )
        assert result == ["/srv/pipeline/outputs:/data/outputs"]

    def test_shorthand_home_rendered_as_dollar_home(self):
        result = expand_volumes_for_script(
            ["~/datasets"], container_home="/home/appuser"
        )
        assert result == ["$HOME/datasets:/data/datasets"]

    def test_shorthand_invalid_basename_raises(self):
        with pytest.raises(ValueError, match="must match"):
            expand_volumes_for_script(["../.."], container_home="/home/appuser")


class TestExpandMountPath:
    def test_tilde_expanded(self):
        ctx = _make_context()
        assert expand_mount_path("~/data", ctx) == "/home/mark/data"

    def test_dollar_home_expanded(self):
        ctx = _make_context()
        assert expand_mount_path("$HOME/data", ctx) == "/home/mark/data"

    def test_workspace_expanded(self):
        ctx = _make_context()
        result = expand_mount_path("$WORKSPACE/output", ctx)
        assert result == "/home/mark/repos/myproject/workspace/output"

    def test_absolute_path_unchanged(self):
        ctx = _make_context()
        assert expand_mount_path("/tmp/data", ctx) == "/tmp/data"

    def test_workspace_without_context_returns_literal(self):
        ctx = _make_context(workspace_user=None)
        assert expand_mount_path("$WORKSPACE/output", ctx) == "$WORKSPACE/output"
