"""Tests for step parsing, command flattening, and validation."""

import pytest

from container_magic.core.registry import load_registry
from container_magic.core.steps import (
    build_command,
    classify_bare_string,
    flatten_command,
    parse_dict_step,
    parse_step,
    quote_arg,
)


class TestQuoteArg:
    def test_simple_string_not_quoted(self):
        assert quote_arg("ffmpeg") == "ffmpeg"

    def test_string_with_spaces_quoted(self):
        assert quote_arg("hello world") == '"hello world"'

    def test_string_with_ampersand_quoted(self):
        assert quote_arg("foo&bar") == '"foo&bar"'

    def test_string_with_pipe_quoted(self):
        assert quote_arg("foo|bar") == '"foo|bar"'

    def test_string_with_dollar_quoted(self):
        assert quote_arg("$HOME") == '"$HOME"'

    def test_string_with_parens_quoted(self):
        assert quote_arg("(test)") == '"(test)"'

    def test_string_with_semicolon_quoted(self):
        assert quote_arg("a;b") == '"a;b"'

    def test_string_with_glob_quoted(self):
        assert quote_arg("*.py") == '"*.py"'

    def test_string_with_backtick_quoted(self):
        assert quote_arg("hello`world") == '"hello`world"'

    def test_hyphen_flag_not_quoted(self):
        assert quote_arg("--verbose") == "--verbose"

    def test_path_not_quoted(self):
        assert quote_arg("/usr/local/bin") == "/usr/local/bin"

    def test_embedded_quotes_escaped(self):
        result = quote_arg('say "hello"')
        assert result == '"say \\"hello\\""'


class TestFlattenCommand:
    def test_string_value(self):
        assert flatten_command("hello") == ["hello"]

    def test_list_of_strings(self):
        assert flatten_command(["a", "b", "c"]) == ["a", "b", "c"]

    def test_none_value(self):
        assert flatten_command(None) == []

    def test_dict_single_key(self):
        assert flatten_command({"install": ["a", "b"]}) == ["install", "a", "b"]

    def test_nested_dict(self):
        result = flatten_command({"-m": {"pytest": ["tests/", "--verbose"]}})
        assert result == ["-m", "pytest", "tests/", "--verbose"]

    def test_dict_with_none_value(self):
        result = flatten_command({"--help": None})
        assert result == ["--help"]

    def test_numeric_values(self):
        result = flatten_command({"--port": 8080})
        assert result == ["--port", "8080"]

    def test_list_with_special_chars_quoted(self):
        result = flatten_command(["normal", "has space", "has$dollar"])
        assert result == ["normal", '"has space"', '"has$dollar"']


class TestBuildCommand:
    def test_no_registry(self):
        result = build_command("apt-get", {"install": ["ffmpeg", "curl"]})
        assert result == "apt-get install ffmpeg curl"

    def test_with_registry_flags(self):
        from container_magic.core.registry import RegistryEntry

        entry = RegistryEntry(flags="-y --no-install-recommends")
        result = build_command("apt-get", {"install": ["ffmpeg", "curl"]}, entry)
        assert "apt-get install -y --no-install-recommends" in result
        assert "ffmpeg" in result
        assert "curl" in result

    def test_with_registry_cleanup(self):
        from container_magic.core.registry import RegistryEntry

        entry = RegistryEntry(
            flags="-y --no-install-recommends",
            cleanup="rm -rf /var/lib/apt/lists/*",
        )
        result = build_command("apt-get", {"install": ["ffmpeg"]}, entry)
        assert "apt-get install -y --no-install-recommends ffmpeg" in result
        assert "rm -rf /var/lib/apt/lists/*" in result

    def test_with_registry_setup(self):
        from container_magic.core.registry import RegistryEntry

        entry = RegistryEntry(
            setup="apt-get update",
            flags="-y --no-install-recommends",
            cleanup="rm -rf /var/lib/apt/lists/*",
        )
        result = build_command("apt-get", {"install": ["ffmpeg"]}, entry)
        assert result.startswith("apt-get update")
        assert "apt-get install -y --no-install-recommends ffmpeg" in result
        assert "rm -rf /var/lib/apt/lists/*" in result

    def test_complex_nested_command(self):
        result = build_command("python", {"-m": {"pytest": ["tests/", "--verbose"]}})
        assert result == "python -m pytest tests/ --verbose"


class TestClassifyBareString:
    def test_canonical_keyword(self):
        result = classify_bare_string("create_user")
        assert result == {"type": "keyword", "keyword": "create_user"}

    def test_become_user_keyword(self):
        result = classify_bare_string("become_user")
        assert result == {"type": "keyword", "keyword": "become_user"}

    def test_become_root_keyword(self):
        result = classify_bare_string("become_root")
        assert result == {"type": "keyword", "keyword": "become_root"}

    def test_hyphenated_create_user_raises(self):
        with pytest.raises(ValueError, match="Unknown step"):
            classify_bare_string("create-user")

    def test_hyphenated_become_user_raises(self):
        with pytest.raises(ValueError, match="Unknown step"):
            classify_bare_string("become-user")

    def test_hyphenated_become_root_raises(self):
        with pytest.raises(ValueError, match="Unknown step"):
            classify_bare_string("become-root")

    def test_switch_user_raises(self):
        with pytest.raises(ValueError, match="Unknown step.*become_user"):
            classify_bare_string("switch_user")

    def test_switch_root_raises(self):
        with pytest.raises(ValueError, match="Unknown step.*become_root"):
            classify_bare_string("switch_root")

    def test_install_system_packages_raises(self):
        with pytest.raises(ValueError, match="Unknown step"):
            classify_bare_string("install_system_packages")

    def test_install_pip_packages_raises(self):
        with pytest.raises(ValueError, match="Unknown step"):
            classify_bare_string("install_pip_packages")

    def test_copy_cached_assets_raises(self):
        with pytest.raises(ValueError, match="Unknown step"):
            classify_bare_string("copy_cached_assets")

    def test_uppercase_passthrough(self):
        result = classify_bare_string("EXPOSE 8080")
        assert result == {"type": "passthrough", "command": "EXPOSE 8080"}

    def test_cmd_passthrough(self):
        result = classify_bare_string('CMD ["python", "app.py"]')
        assert result == {"type": "passthrough", "command": 'CMD ["python", "app.py"]'}

    def test_env_passthrough(self):
        result = classify_bare_string("ENV FOO=bar")
        assert result == {"type": "passthrough", "command": "ENV FOO=bar"}

    def test_run_passthrough(self):
        result = classify_bare_string("RUN echo hello")
        assert result == {"type": "passthrough", "command": "RUN echo hello"}

    def test_shell_command(self):
        result = classify_bare_string("apt-get update && apt-get install -y vim")
        assert result["type"] == "run"
        assert "apt-get update" in result["command"]

    def test_unknown_keyword_raises_error(self):
        with pytest.raises(ValueError, match="Unknown step keyword"):
            classify_bare_string("crate-user")

    def test_unknown_keyword_suggests_close_match(self):
        with pytest.raises(ValueError, match="create.user"):
            classify_bare_string("crate-user")

    def test_v1_copy_with_args(self):
        result = classify_bare_string("copy docs/Gemfile /tmp/")
        assert result["type"] == "copy_v1"
        assert result["args"] == "docs/Gemfile /tmp/"
        assert result["chown"] == "context"

    def test_v1_copy_as_user_with_args(self):
        result = classify_bare_string("copy_as_user app /app")
        assert result["type"] == "copy_v1"
        assert result["args"] == "app /app"
        assert result["chown"] is True

    def test_v1_copy_as_root_with_args(self):
        result = classify_bare_string("copy_as_root config /etc/config")
        assert result["type"] == "copy_v1"
        assert result["args"] == "config /etc/config"
        assert result["chown"] is False

    def test_v1_copy_empty_args_raises(self):
        with pytest.raises(ValueError, match="requires arguments"):
            classify_bare_string("copy ")

    def test_v1_copy_as_user_empty_args_raises(self):
        with pytest.raises(ValueError, match="requires arguments"):
            classify_bare_string("copy_as_user ")


class TestParseDictStep:
    def setup_method(self):
        self.registry = load_registry()

    def test_run_string(self):
        result = parse_dict_step({"run": "echo hello"}, self.registry)
        assert result == {"type": "run", "command": "echo hello"}

    def test_run_list(self):
        result = parse_dict_step(
            {"run": ["apt-get update", "apt-get install -y curl"]},
            self.registry,
        )
        assert result["type"] == "run"
        assert "apt-get update" in result["command"]
        assert "apt-get install -y curl" in result["command"]
        assert "&&" in result["command"]

    def test_copy_string(self):
        result = parse_dict_step({"copy": "app /app"}, self.registry)
        assert result == {"type": "copy_v2", "args_list": ["app /app"]}

    def test_copy_list(self):
        result = parse_dict_step(
            {"copy": ["config /etc/config", "app /home/user/app"]},
            self.registry,
        )
        assert result == {
            "type": "copy_v2",
            "args_list": ["config /etc/config", "app /home/user/app"],
        }

    def test_env_dict(self):
        result = parse_dict_step(
            {"env": {"APP_PORT": "8080", "DEBUG": "true"}},
            self.registry,
        )
        assert result == {
            "type": "env",
            "vars": {"APP_PORT": "8080", "DEBUG": "true"},
        }

    def test_env_non_dict_raises(self):
        with pytest.raises(ValueError, match="must be a dict"):
            parse_dict_step({"env": "FOO=bar"}, self.registry)

    def test_apt_get_install_with_registry(self):
        result = parse_dict_step(
            {"apt-get": {"install": ["ffmpeg", "curl"]}},
            self.registry,
        )
        assert result["type"] == "run"
        assert "apt-get update" in result["command"]
        assert "-y --no-install-recommends" in result["command"]
        assert "ffmpeg" in result["command"]
        assert "curl" in result["command"]
        assert "rm -rf /var/lib/apt/lists/*" in result["command"]

    def test_pip_install_with_registry(self):
        result = parse_dict_step(
            {"pip": {"install": ["numpy", "flask"]}},
            self.registry,
        )
        assert result["type"] == "run"
        assert "--no-cache-dir" in result["command"]
        assert "numpy" in result["command"]

    def test_unknown_tool_no_flags(self):
        result = parse_dict_step(
            {"my-tool": {"deploy": ["app"]}},
            self.registry,
        )
        assert result["type"] == "run"
        assert result["command"] == "my-tool deploy app"

    def test_multiple_keys_raises(self):
        with pytest.raises(ValueError, match="single key"):
            parse_dict_step({"run": "a", "copy": "b"}, self.registry)

    def test_copy_invalid_type_raises(self):
        with pytest.raises(ValueError, match="must be a string or list"):
            parse_dict_step({"copy": 42}, self.registry)


class TestParseStep:
    def setup_method(self):
        self.registry = load_registry()

    def test_string_step(self):
        result = parse_step("create_user", self.registry)
        assert result["type"] == "keyword"
        assert result["keyword"] == "create_user"

    def test_dict_step(self):
        result = parse_step({"run": "echo hello"}, self.registry)
        assert result["type"] == "run"

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="must be a string or dict"):
            parse_step(42, self.registry)

    def test_apt_get_full_pipeline(self):
        result = parse_step(
            {"apt-get": {"install": ["ffmpeg", "curl"]}},
            self.registry,
        )
        assert result["type"] == "run"
        assert "apt-get update" in result["command"]
        assert "apt-get install -y --no-install-recommends" in result["command"]
        assert "ffmpeg" in result["command"]
        assert "curl" in result["command"]
        assert "rm -rf /var/lib/apt/lists/*" in result["command"]

    def test_apk_add_full_pipeline(self):
        result = parse_step(
            {"apk": {"add": ["curl", "git"]}},
            self.registry,
        )
        assert result["type"] == "run"
        assert "apk add --no-cache" in result["command"]
        assert "curl" in result["command"]
        assert "git" in result["command"]

    def test_dnf_install_full_pipeline(self):
        result = parse_step(
            {"dnf": {"install": ["curl", "git"]}},
            self.registry,
        )
        assert result["type"] == "run"
        assert "dnf install -y" in result["command"]
        assert "curl" in result["command"]
        assert "git" in result["command"]
        assert "dnf clean all" in result["command"]
