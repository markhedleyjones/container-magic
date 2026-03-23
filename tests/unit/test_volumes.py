"""Unit tests for volume SELinux labelling."""

from container_magic.core.volumes import ensure_selinux_label, label_volumes


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
        assert ensure_selinux_label("myvolume:/container/path") == "myvolume:/container/path:z"

    def test_compound_options_with_nocopy(self):
        assert ensure_selinux_label("/host:/container:ro,nocopy") == "/host:/container:ro,nocopy,z"


class TestLabelVolumes:
    def test_empty_list(self):
        assert label_volumes([]) == []

    def test_mixed_volumes(self):
        result = label_volumes([
            "/tmp/data:/data:ro",
            "/var/log:/logs",
            "/host:/container:z",
        ])
        assert result == [
            "/tmp/data:/data:ro,z",
            "/var/log:/logs:z",
            "/host:/container:z",
        ]
