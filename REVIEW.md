# Code Review

Full code review performed 2026-02-23. Issues grouped into batches that can be
tackled together, ordered by priority.


## Batch 1: Dockerfile output correctness

These produce broken or incorrect Dockerfiles. Highest priority because they
affect every user who hits the relevant code path.

### 1.1 ENV values with spaces produce broken output

`templates/Dockerfile.j2:33-35`

`ENV {{ key }}={{ value }}` without quoting. `MY_VAR=hello world` is parsed by
Docker as two assignments: `MY_VAR=hello` and `world=`. Values must be quoted:
`ENV {{ key }}="{{ value }}"`.

### 1.2 Missing Dockerfile instruction passthrough

`templates/Dockerfile.j2:147`

Custom steps starting with `ARG`, `CMD`, `ENTRYPOINT`, `HEALTHCHECK`, `SHELL`,
or `STOPSIGNAL` get wrapped with a `RUN` prefix. Only `COPY`, `ADD`, `ENV`,
`WORKDIR`, `USER`, `LABEL`, `EXPOSE`, `VOLUME`, and `RUN` are currently
recognised.

### 1.3 Multi-line step starting with non-RUN instruction (won't fix)

`generators/dockerfile.py:160-163`

Lines get joined with `&&`, so a multi-line step starting with `ENV FOO=bar`
produces `ENV FOO=bar && echo hello` which is invalid Dockerfile syntax.

Not fixing: the scenario is contrived (users should write separate list items),
and any fix risks breaking legitimate multi-line RUN steps that happen to
contain instruction keywords like `RUN` itself.

### 1.4 Empty copy step arguments accepted silently

`generators/dockerfile.py:149-156`

`steps: ["copy "]` (trailing space, no arguments) produces `COPY ` with no
source or destination.


## Batch 2: User and home path handling

Related bugs around user configuration flowing through to generated files.

### 2.1 `user_cfg.name` can be None, producing `USER_NAME=None`

`generators/dockerfile.py:290,304,322`

A config like `user: { production: { uid: 1000 } }` without `name` passes
validation but produces literal `ARG USER_NAME=None` and
`ARG USER_HOME=/home/None` in the Dockerfile.

Fix: either require `name` when `host` is not true, or guard in the generator.

### 2.2 run.sh ignores custom home path

`generators/run_script.py:30-38`

Hardcodes `f"/home/{production_user}"` instead of using `user_cfg.home`. Compare
with `standalone_commands.py:56-58` which handles it correctly.

### 2.3 UID/GID 0 treated as falsy

`generators/dockerfile.py:320-321`

`user_cfg.uid or 1000` treats `uid: 0` as falsy, overriding it to 1000. Should
use `user_cfg.uid if user_cfg.uid is not None else 1000`.

### 2.4 `to_yaml` serialises `steps` as `build_steps`

`core/config.py:260,359`

The `alias="build_steps"` combined with `by_alias=True` in `to_yaml()` means
round-tripping a config rewrites `steps:` to `build_steps:`. Users who run
`cm init` followed by `cm update` would see their field name change.


## Batch 3: Podman compatibility

Issues where behaviour differs between Docker and Podman. These can all be
addressed together since they involve the same template files.

### 3.1 Container name substring matching in Podman

`Justfile.j2:256`, `custom_command.j2`

`ps --filter name=X` does substring matching in Podman, so `myapp` matches
`myapp-dev`. Needs `^X$` anchoring for Podman.

### 3.2 `--userns=keep-id` and `--env-host=false` missing from production scripts

`Justfile.j2` includes these Podman-specific flags but `run.sh.j2` and
`standalone_command.sh.j2` do not. Production Podman containers have different
user-namespace behaviour than development ones.

### 3.3 `--security-opt=label=disable` missing from production scripts

Justfile has this for SELinux/X11 compatibility but the production scripts omit
it.

### 3.4 `--hostname` inconsistency

`run.sh.j2:59` sets `--hostname` but `Justfile.j2` and `custom_command.j2` do
not.

### 3.5 TTY detection: `-t 0` vs `-t 1`

`custom_command.j2` tests stdin (`-t 0`), `Justfile.j2` tests stdout (`-t 1`).
These give different results in pipelines.

### 3.6 `:z` SELinux label not applied to user-defined volumes

User-defined volumes from `runtime.volumes` are passed through verbatim. On
SELinux systems with Podman, these fail with permission denied unless the user
manually adds `:z`.


## Batch 4: Config validation gaps

Missing validation that lets bad configs through silently. These can be tackled
together as they're all in `config.py` or `dockerfile.py` validation logic.

### 4.1 Step keyword typos silently become RUN commands

`generators/dockerfile.py`

`instal_system_packages` (typo) produces `RUN instal_system_packages`. No
validation against the set of known step keywords. This is probably the most
likely user mistake.

### 4.2 No validation that package manager matches base image

A user can specify `packages.apk: [curl]` on a Debian image. The template emits
all non-empty package blocks regardless, producing `apk add` in a Debian
Dockerfile.

### 4.3 `from_yaml` crashes on empty YAML

`core/config.py:340-342`

`yaml.safe_load()` returns `None` for empty files, then `cls(**None)` throws an
unhelpful TypeError. Should also catch `yaml.YAMLError` for syntax errors and
Pydantic `ValidationError` for schema errors, producing clear messages.

### 4.4 No warning if package install runs after `become_user`

`apt-get install` or `pip install` after `become_user` will fail with permission
errors at build time. Could warn at config validation time.

### 4.5 `cm init --here` silently overwrites existing config

`cli/main.py:182-185`

No check for an existing config file before overwriting everything.

### 4.6 Deprecated `network` + `network_mode` conflict silently ignored

`core/config.py:183-192`

If both are specified, the deprecated field is silently dropped. Should warn or
error about the conflict.


## Batch 5: Runtime script consistency

The Justfile, run.sh, standalone commands, and custom commands should produce
equivalent container behaviour but have drifted apart.

### 5.1 Justfile force flag consumed by Jinja2

`Justfile.j2:33`

`{{ force }}` is a Jinja2 variable reference, rendered as empty string. Should be
`{{ '{{force}}' }}` so it passes through as Just syntax. The `--force` flag for
`just build` has never worked.

### 5.2 run.sh uses `$*` instead of `"$@"`

`run.sh.j2`

`$*` loses argument boundaries. A command like `./run.sh echo "hello world"`
would split `hello world` into two arguments.

### 5.3 Justfile has exec-into-running-container, run.sh does not

`Justfile.j2:255-273`

`just run` when a container is already running does `exec`. `./run.sh` with the
same scenario fails with "name already in use".

### 5.4 Standalone command workdir differs from run.sh

`standalone_command.sh.j2:180` uses `${WORKDIR}` (user home).
`run.sh.j2:226` uses `${WORKDIR}/${WORKSPACE_NAME}`.

### 5.5 `realpath --relative-to` not available on macOS

`Justfile.j2:219`

GNU coreutils flag, not available on macOS BSD realpath. Fails silently due to
`2>/dev/null || echo ""` fallback, causing workdir to always resolve to project
root on macOS.


## Batch 6: Documentation

These can be done in one pass through the docs.

### 6.1 `cm build`, `cm run`, `cm shell`, `cm generate` undocumented

The scaffold output tells users to run `cm build` but it's not in any docs page.

### 6.2 Justfile recipes undocumented

`just stop`, `just clean`, `just clean-images`, `just build-production`,
`just shell` — no documentation.

### 6.3 Named containers and container reuse undocumented

Containers are named `<project>-development` / `<project>`. The exec-into-
running behaviour is not documented.

### 6.4 `cm build` vs `just build` inconsistency

`cm init` output says `cm build`, docs say `just build`.

### 6.5 Config fields undocumented

`stage.package_manager`, `stage.shell`, `--in-place` alias, `--path` option,
`--force` flag for `just build`, `ipc` in command options table.

### 6.6 `$WORKDIR` misleadingly documented

Documented as "working directory" but actually equals user home directory, not
workspace.

### 6.7 `auto_update` placement ambiguous in docs

Docs say "set `auto_update: false`" without clarifying it goes under `project:`.

### 6.8 Quick start image tag inconsistent between pages

README uses `python` (no tag), getting-started uses `python:3.11`.

### 6.9 Error message text mismatch

`troubleshooting.md:52` says `production.user` but the config path is
`user.production`.


## Batch 7: Dead code and cleanup

Low-risk housekeeping, can be done any time.

### 7.1 Dead default stage creation

`generators/dockerfile.py:260-270`

Default development/production stages can never be created because the config
validator already requires both stages.

### 7.2 Unused `production_user` parameter

`generators/dockerfile.py:87`

`process_stage_steps` accepts `production_user` but never uses it.

### 7.3 Duplicated config discovery logic

`cli/main.py:433-439,479-485`

`run_main()` and `build_main()` duplicate the parent-directory walk without
using `find_config_file()`, and lack the both-files-exist conflict check.

### 7.4 `which` not portable

`cli/main.py:320,339,416,449,524`

Should use `shutil.which()` instead of `subprocess.run(["which", ...])`.

### 7.5 `select_autoescape()` misleading in shell template generators

`generators/justfile.py:36`, `generators/standalone_commands.py:36`

`select_autoescape()` with no arguments is a no-op for `.j2` files. Use
`autoescape=False` to make intent clear.

### 7.6 `find_config_file` uses `sys.exit()` instead of raising an exception

`core/config.py:47-48,56-59`

Makes the function untestable and unsuitable for library use.

### 7.7 Blank line inconsistency in package blocks

`templates/Dockerfile.j2:40-58`

apk and dnf blocks have trailing blank lines, apt block does not.

### 7.8 `copy_workspace`/`cached_assets` chown logic differs from `copy`

`templates/Dockerfile.j2:127-145`

The former uses `needs_user_args` (always chown if user exists), the latter uses
runtime `user_is_active` (only after `become_user`). Not necessarily a bug but
an inconsistency in the mental model.

### 7.9 All stages get WORKDIR/USER_HOME even builder stages

`generators/dockerfile.py:304`

Builder stages that compile code get `WORKDIR` forced to the user's home
directory, which may conflict with build commands.

### 7.10 Empty pip_packages emits orphaned comment

`templates/Dockerfile.j2:59-65`

When `install_pip_packages` is in steps but the list is empty, the template
emits `# Install Python pip packages` with no following RUN instruction.


## Batch 8: Test improvements

Can be tackled incrementally.

### 8.1 Tautological assertion

`test_user_validation.py:271`

`assert "USER_UID" not in content or "root" in content` — the second condition
is almost always true (most Dockerfiles contain "root"), making the assertion
meaningless.

### 8.2 Duplicated test utilities

`tests/integration/test_generation.py` redefines validation functions that
already exist in `tests/utils/validation.py`.

### 8.3 Missing test coverage

No tests for: `from_yaml` error handling, `find_config_file`, deprecated
`build_steps` alias, `cm shell`, `cm generate`, `run_main()`/`build_main()`
entry points, cache subcommands, spaces in project paths, multiple package
managers in one stage, `cm update` with stale configs, `user.development` with
fixed values.
