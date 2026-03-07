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
    @pytest.mark.parametrize(
        "keyword",
        [
            "copy_workspace",
            "create_user",
            "become_user",
            "become_root",
            "copy_as_user",
            "copy_as_root",
            "create-user",
            "become-user",
            "become-root",
            "switch_user",
            "switch_root",
            "install_system_packages",
            "install_pip_packages",
            "copy_cached_assets",
            "copy-cached-assets",
            "copy-workspace",
        ],
    )
    def test_removed_keywords_raise(self, keyword):
        with pytest.raises(ValueError, match="Unknown step"):
            classify_bare_string(keyword)

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
            classify_bare_string("crate_workspace")

    def test_v1_copy_with_args(self):
        result = classify_bare_string("copy docs/Gemfile /tmp/")
        assert result["type"] == "copy_v1"
        assert result["args"] == "docs/Gemfile /tmp/"
        assert result["chown"] == "context"

    def test_v1_copy_empty_args_raises(self):
        with pytest.raises(ValueError, match="requires arguments"):
            classify_bare_string("copy ")


class TestParseDictStep:
    def setup_method(self):
        self.registry = load_registry()

    def test_create_user_string(self):
        result = parse_dict_step({"create_user": "appuser"}, self.registry)
        assert result == {
            "type": "create_user",
            "username": "appuser",
            "uid": None,
            "gid": None,
        }

    def test_create_user_dict(self):
        result = parse_dict_step(
            {"create_user": {"name": "app", "uid": 2000, "gid": 2000}}, self.registry
        )
        assert result == {
            "type": "create_user",
            "username": "app",
            "uid": 2000,
            "gid": 2000,
        }

    def test_create_user_dict_name_only(self):
        result = parse_dict_step({"create_user": {"name": "app"}}, self.registry)
        assert result == {
            "type": "create_user",
            "username": "app",
            "uid": None,
            "gid": None,
        }

    def test_create_user_empty_raises(self):
        with pytest.raises(ValueError, match="non-empty username"):
            parse_dict_step({"create_user": ""}, self.registry)

    def test_create_user_dict_missing_name_raises(self):
        with pytest.raises(ValueError, match="must have a 'name' field"):
            parse_dict_step({"create_user": {"uid": 1000}}, self.registry)

    def test_old_create_syntax_raises_migration_error(self):
        with pytest.raises(ValueError, match="no longer supported"):
            parse_dict_step({"create": "user"}, self.registry)

    def test_become_user(self):
        result = parse_dict_step({"become": "appuser"}, self.registry)
        assert result == {"type": "become", "name": "appuser"}

    def test_become_root(self):
        result = parse_dict_step({"become": "root"}, self.registry)
        assert result == {"type": "become", "name": "root"}

    def test_become_empty_raises(self):
        with pytest.raises(ValueError, match="non-empty username"):
            parse_dict_step({"become": ""}, self.registry)

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

    def test_env_list_of_dicts(self):
        result = parse_dict_step(
            {"env": [{"APP_PORT": "8080"}, {"DEBUG": "true"}]},
            self.registry,
        )
        assert result == {
            "type": "env",
            "vars": {"APP_PORT": "8080", "DEBUG": "true"},
        }

    def test_env_list_of_strings(self):
        result = parse_dict_step(
            {"env": ["APP_PORT=8080", "DEBUG=true"]},
            self.registry,
        )
        assert result == {
            "type": "env",
            "vars": {"APP_PORT": "8080", "DEBUG": "true"},
        }

    def test_env_list_mixed(self):
        result = parse_dict_step(
            {"env": [{"APP_PORT": "8080"}, "DEBUG=true"]},
            self.registry,
        )
        assert result == {
            "type": "env",
            "vars": {"APP_PORT": "8080", "DEBUG": "true"},
        }

    def test_env_list_invalid_item_raises(self):
        with pytest.raises(ValueError, match="list items must be"):
            parse_dict_step({"env": [42]}, self.registry)

    def test_env_non_dict_or_list_raises(self):
        with pytest.raises(ValueError, match="must be a dict or list"):
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

    def test_copy_workspace_removed(self):
        with pytest.raises(ValueError, match="copy: workspace"):
            parse_step("copy_workspace", self.registry)

    def test_dict_step(self):
        result = parse_step({"run": "echo hello"}, self.registry)
        assert result["type"] == "run"

    def test_create_user_dict_step(self):
        result = parse_step({"create_user": "appuser"}, self.registry)
        assert result["type"] == "create_user"
        assert result["username"] == "appuser"

    def test_become_dict_step(self):
        result = parse_step({"become": "appuser"}, self.registry)
        assert result["type"] == "become"
        assert result["name"] == "appuser"

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
