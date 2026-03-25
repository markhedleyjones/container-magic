# CHANGELOG

<!-- version list -->

## v4.1.2 (2026-03-25)

### Bug Fixes

- Chown venv to runtime user for development writability
  ([`14c2a18`](https://github.com/markhedleyjones/container-magic/commit/14c2a18f81f1d33ae7525ff1410f2c78d7ce5a21))

- Rename ambiguous loop variable in venv chown test
  ([`50a6df2`](https://github.com/markhedleyjones/container-magic/commit/50a6df2e056b04e80913b271f060847c6e335728))


## v4.1.1 (2026-03-25)

### Bug Fixes

- Split mount prefixes with trailing space into separate arguments
  ([`df160bf`](https://github.com/markhedleyjones/container-magic/commit/df160bf2b6430e5bfa0f57e219dc73510df7a458))


## v4.1.0 (2026-03-24)

### Documentation

- Document variable expansion in volume paths
  ([`a24a03b`](https://github.com/markhedleyjones/container-magic/commit/a24a03b336110edbb39b5303275dba664a5cbde7))

- Fix README tagline to accurately describe zero-dependency output
  ([`572ad33`](https://github.com/markhedleyjones/container-magic/commit/572ad338475ea0078fbde7e87157744e3e8838d0))

- Rewrite README for implicit user handling and clearer value proposition
  ([`340ea7e`](https://github.com/markhedleyjones/container-magic/commit/340ea7e5df764aaa3347eab0b54542f90cb21e56))

### Features

- Variable expansion in volume paths
  ([`c494944`](https://github.com/markhedleyjones/container-magic/commit/c494944a28807e96b4d88e92a45f17ccd2012ac2))


## v4.0.0 (2026-03-23)

### Bug Fixes

- Remove unused distro_shell variable and Path import
  ([`5206f54`](https://github.com/markhedleyjones/container-magic/commit/5206f546141a2d1a5e95a20f4fc8d0c9f4d3642d))

### Documentation

- Update all documentation for implicit user handling and distro field
  ([`a9e6f83`](https://github.com/markhedleyjones/container-magic/commit/a9e6f83987944d5634ee787426f7134606729271))

### Features

- Add distro config field with inheritance
  ([`5abfcf8`](https://github.com/markhedleyjones/container-magic/commit/5abfcf8e791b8738a1f5c64b6bc0a937306a3415))

- Implicit user creation and become when names.user is not root
  ([`5e58f01`](https://github.com/markhedleyjones/container-magic/commit/5e58f01f08ba72bb9fe7b91664a442d11b24d0ca))

### Refactoring

- Move shell from stages to runtime config
  ([`d5b8e3e`](https://github.com/markhedleyjones/container-magic/commit/d5b8e3e37f5af29b8b08e3ecedee4970107bdbab))

### Testing

- Standardise base images and add end-to-end scenarios
  ([`4c88569`](https://github.com/markhedleyjones/container-magic/commit/4c885699e5edbd8e3eb5687349216e73b4fa1f14))


## v3.2.0 (2026-03-23)

### Features

- **pip**: Auto-create virtual environment for pip steps
  ([#42](https://github.com/markhedleyjones/container-magic/pull/42),
  [`d7e35e5`](https://github.com/markhedleyjones/container-magic/commit/d7e35e588dc4f008bc3e1f2c44976939388d6075))

### Testing

- Add linter validation for generated Dockerfiles and shell scripts
  ([#41](https://github.com/markhedleyjones/container-magic/pull/41),
  [`c9de5b0`](https://github.com/markhedleyjones/container-magic/commit/c9de5b0e3b526fc2c64370c2a140671fa4dc89e0))


## v3.1.3 (2026-03-23)

### Bug Fixes

- Run custom commands from workspace directory
  ([#40](https://github.com/markhedleyjones/container-magic/pull/40),
  [`aac5aa1`](https://github.com/markhedleyjones/container-magic/commit/aac5aa124c40a004f266ee1fe0797e4137d6c1b7))


## v3.1.2 (2026-03-23)

### Bug Fixes

- Add SELinux :z labels to runtime volumes
  ([#39](https://github.com/markhedleyjones/container-magic/pull/39),
  [`b221176`](https://github.com/markhedleyjones/container-magic/commit/b22117622f404d0fc4c6af1d83e0b79fed726344))


## v3.1.1 (2026-03-23)

### Bug Fixes

- Add SELinux labels to display and audio feature mounts
  ([#38](https://github.com/markhedleyjones/container-magic/pull/38),
  [`48874cb`](https://github.com/markhedleyjones/container-magic/commit/48874cbd0b3d5fcedab09168f1f9342fb66581a5))


## v3.1.0 (2026-03-15)

### Features

- **build**: Accept arbitrary build targets
  ([#37](https://github.com/markhedleyjones/container-magic/pull/37),
  [`4d6756f`](https://github.com/markhedleyjones/container-magic/commit/4d6756f12aa4587ebfe3302073b869e06ea3cdb1))

### Refactoring

- **test**: Reduce builder test boilerplate with fixture
  ([#37](https://github.com/markhedleyjones/container-magic/pull/37),
  [`4d6756f`](https://github.com/markhedleyjones/container-magic/commit/4d6756f12aa4587ebfe3302073b869e06ea3cdb1))

### Testing

- **build**: Update tests for arbitrary build targets
  ([#37](https://github.com/markhedleyjones/container-magic/pull/37),
  [`4d6756f`](https://github.com/markhedleyjones/container-magic/commit/4d6756f12aa4587ebfe3302073b869e06ea3cdb1))


## v3.0.0 (2026-03-11)

### Bug Fixes

- Add container rm to clean, workdir to exec, conditional xhost
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Address code review issues in runner, CLI, and config
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Capture user cwd before chdir in cm run
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Clean up stale Justfile references and dead code
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Escape Jinja2 comment markers in run.sh template
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Manifest cleanup without overwriting xhost trap
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Mount parsing in run.sh and shell-safe command handling
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Only warn about container-magic generated Justfiles
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Reject auto_update field instead of warning
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Remove unicode checkmark from cache clear output
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Use shlex.join to preserve argument quoting
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

### Chores

- Clean up stale files and update cm.yaml to current format
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Remove CLAUDE.md and REVIEW.md from .gitignore
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Remove migration validators for unreleased features
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

### Documentation

- Add runtime flag passthrough documentation
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Add stop/clean commands and v2 migration guide
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Document working directory behaviour and exec/shell
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Replace inputs/outputs with mounts documentation
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Update documentation for v3 Justfile removal
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

### Features

- Add cm stop and cm clean commands
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Prefer docker over podman in auto-detection
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Replace inputs/outputs with unified mounts block
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Replace Justfile with Python-native build and run commands
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Replace Justfile with Python-native commands
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Runtime flag passthrough with -- separator
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

### Performance Improvements

- Scan workspace symlinks once and skip symlinked directories
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

### Refactoring

- Consolidate build staging into .cm-cache/
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Remove container-magic.yaml support
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Remove standalone build and run entry points
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Update runner to use mounts instead of inputs/outputs
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Use exec form for ad-hoc commands instead of shell wrapping
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

### Testing

- Add mount config schema tests ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Add tests for runtime flag passthrough parsing
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Add unit tests for runner and builder modules
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))

- Update tests for v3 Justfile removal
  ([#36](https://github.com/markhedleyjones/container-magic/pull/36),
  [`575f9dd`](https://github.com/markhedleyjones/container-magic/commit/575f9ddf0638003592f0279372f1ca3b4de85bf0))


## v2.2.1 (2026-03-09)

### Bug Fixes

- Add missing .env and privileged support to production templates
  ([#35](https://github.com/markhedleyjones/container-magic/pull/35),
  [`a22ec5e`](https://github.com/markhedleyjones/container-magic/commit/a22ec5ee38a272a84dedafcdc09464398b234422))


## v2.2.0 (2026-03-09)

### Bug Fixes

- **ci**: Bump test fixture from ubuntu 22.04 to 24.04
  ([#34](https://github.com/markhedleyjones/container-magic/pull/34),
  [`71b7885`](https://github.com/markhedleyjones/container-magic/commit/71b78853d0e60f36daaf77cd0a4cc1bb378ccb4c))

- **ci**: Use python:3-slim instead of ubuntu base in test fixture
  ([#34](https://github.com/markhedleyjones/container-magic/pull/34),
  [`71b7885`](https://github.com/markhedleyjones/container-magic/commit/71b78853d0e60f36daaf77cd0a4cc1bb378ccb4c))

### Documentation

- Add environment file section to configuration
  ([#33](https://github.com/markhedleyjones/container-magic/pull/33),
  [`a995bdf`](https://github.com/markhedleyjones/container-magic/commit/a995bdfcbbe2f8bce26f5600e514c5350583aeb6))

### Features

- Load .env file as environment variables in containers
  ([#33](https://github.com/markhedleyjones/container-magic/pull/33),
  [`a995bdf`](https://github.com/markhedleyjones/container-magic/commit/a995bdfcbbe2f8bce26f5600e514c5350583aeb6))

### Testing

- **ci**: Promote apt-get installation test to run in CI
  ([#34](https://github.com/markhedleyjones/container-magic/pull/34),
  [`71b7885`](https://github.com/markhedleyjones/container-magic/commit/71b78853d0e60f36daaf77cd0a4cc1bb378ccb4c))


## v2.1.0 (2026-03-09)

### Bug Fixes

- Use os.readlink for Python 3.8 compatibility
  ([#32](https://github.com/markhedleyjones/container-magic/pull/32),
  [`8c5195e`](https://github.com/markhedleyjones/container-magic/commit/8c5195e22b7ea4514e106d98379818af38403ea6))

### Documentation

- Add symlink documentation and dev/production callouts
  ([#32](https://github.com/markhedleyjones/container-magic/pull/32),
  [`8c5195e`](https://github.com/markhedleyjones/container-magic/commit/8c5195e22b7ea4514e106d98379818af38403ea6))

- Update README for v2 config syntax
  ([`611ac0f`](https://github.com/markhedleyjones/container-magic/commit/611ac0fc344a3f6918d34cbb7f53adf19c967a5f))

### Features

- Symlink-aware workspace handling
  ([#32](https://github.com/markhedleyjones/container-magic/pull/32),
  [`8c5195e`](https://github.com/markhedleyjones/container-magic/commit/8c5195e22b7ea4514e106d98379818af38403ea6))


## v2.0.0 (2026-03-09)

### Bug Fixes

- Address review findings
  ([`7ced3c7`](https://github.com/markhedleyjones/container-magic/commit/7ced3c753d28dce947925871a918c27a7b716a99))

- Clean up user-facing error messages and remove stale --compact flag
  ([`8bcd2ad`](https://github.com/markhedleyjones/container-magic/commit/8bcd2adb5dc441b85491846bf300e7b796c9a0f2))

- Correct multi-line run step detection and remove template comments
  ([`899b0ca`](https://github.com/markhedleyjones/container-magic/commit/899b0cab5deff4e791d72968cf9417217e4f8c99))

- Registry setup field and double-continuation in generated commands
  ([`a8c54b6`](https://github.com/markhedleyjones/container-magic/commit/a8c54b6a4b39881b0f3b83944e2fea917b08f658))

- Rename ambiguous loop variable in test
  ([`6214510`](https://github.com/markhedleyjones/container-magic/commit/6214510884e2edc8c32df42aa9c86eb1379641a3))

- Rename ambiguous variable in test
  ([`b0ec7cd`](https://github.com/markhedleyjones/container-magic/commit/b0ec7cdd3b857f8e1cfe073a5e06bffc6697b413))

- Rename remaining names.project references in integration tests
  ([`e8c7ab0`](https://github.com/markhedleyjones/container-magic/commit/e8c7ab001fef43ee1931106ae1e983ec74b051ad))

- Update remaining test files to v2 names config syntax
  ([`853944c`](https://github.com/markhedleyjones/container-magic/commit/853944cf82c98e4cafefa85c4b8a2a951ac752e7))

### Chores

- Add examples directory to gitignore
  ([`e5dd99d`](https://github.com/markhedleyjones/container-magic/commit/e5dd99d2f935aecd00766964e543a2d569e23cf9))

### Documentation

- Document env step syntax and vary example usernames
  ([`5bb0285`](https://github.com/markhedleyjones/container-magic/commit/5bb02856226bf9fabb6bcd1474e45dd024f78b42))

- Document run list form and remove pipe block examples
  ([`7ea8d9a`](https://github.com/markhedleyjones/container-magic/commit/7ea8d9af40db6d79fe698f0edc4439e5c226451f))

- Expand package lists and document registry defaults
  ([`70f7e6c`](https://github.com/markhedleyjones/container-magic/commit/70f7e6cfa825a8b6a61a9dc61fbaf284c8e40c36))

- Fix mixed ownership example in user-handling
  ([`73c5baf`](https://github.com/markhedleyjones/container-magic/commit/73c5bafe6cacc734b6f128228b53b543e22fb073))

- Standardise on copy: dict form throughout
  ([`a585a8f`](https://github.com/markhedleyjones/container-magic/commit/a585a8fa6ca13a824d799e78324e2df50d060bfc))

- Update documentation for create_user and copy: workspace
  ([`222ff38`](https://github.com/markhedleyjones/container-magic/commit/222ff387df2717a45636b269ad858099c6f986e1))

- Update documentation for v2
  ([`917f985`](https://github.com/markhedleyjones/container-magic/commit/917f9853e0e212b1b7f3b84317ea08c8dbe1572d))

- Update for v2 config syntax
  ([`cd6c4c7`](https://github.com/markhedleyjones/container-magic/commit/cd6c4c75789688ec73ab7681b5516ba680e30983))

- Use auxiliary files in copy examples, not application code
  ([`461ba20`](https://github.com/markhedleyjones/container-magic/commit/461ba201f7691bac96f05727b53a9c06e247c64d))

### Features

- Clean up Dockerfile preamble and merge ENV output
  ([`16f7b81`](https://github.com/markhedleyjones/container-magic/commit/16f7b81d1612e29f9597880bb5485f85755d4aec))

- Drop all backwards compatibility for v2
  ([`f17b9ad`](https://github.com/markhedleyjones/container-magic/commit/f17b9ada4fd809f21e949a5a2976089230ac3f4a))

- Finalise v2 config syntax
  ([`1af548a`](https://github.com/markhedleyjones/container-magic/commit/1af548aba8701fc7add3b1cb6d26ab5755479998))

- Project-level assets with copy resolution
  ([`82d75d4`](https://github.com/markhedleyjones/container-magic/commit/82d75d44f7dd15fbda1543c7f1578e6621132e8e))

- Remove packages and env config from stages
  ([`2f5a450`](https://github.com/markhedleyjones/container-magic/commit/2f5a45082dcc217af10ff29d4121d43531885da8))

- Replace project config with names block
  ([`c7e4ccc`](https://github.com/markhedleyjones/container-magic/commit/c7e4ccc3887fb43509dc124460c08abd3fea0eb3))

- Replace user config with create_user step
  ([`88356c9`](https://github.com/markhedleyjones/container-magic/commit/88356c9a9ff391d5729be4030328fe99c8e791b6))

- Structured step syntax (v2) with command registry
  ([`dbe414d`](https://github.com/markhedleyjones/container-magic/commit/dbe414de84612c1087e5f41a04725cfbe10a6c6b))

- Support list syntax for env steps
  ([`622c0c1`](https://github.com/markhedleyjones/container-magic/commit/622c0c192fa34bbd0a1a8a23f4a65cd28d557f98))

- Use nonroot as default username in cm init
  ([`a90cc63`](https://github.com/markhedleyjones/container-magic/commit/a90cc633114aa162edf7daa1949b1838b998c89f))

### Testing

- Remove redundant tests and parametrise near-duplicates
  ([`d7648d0`](https://github.com/markhedleyjones/container-magic/commit/d7648d047f3510f362e5b30c8c6672febfe402fd))

- Remove ROS1 Noetic integration test
  ([`fae9ce2`](https://github.com/markhedleyjones/container-magic/commit/fae9ce26ace5d8a4bf484dee3be5597474a65cd3))

- Update tests for create_user step and copy: workspace
  ([`5ea398b`](https://github.com/markhedleyjones/container-magic/commit/5ea398bcae17a87139c94cfdc292fa4daa3e182e))


## v1.12.5 (2026-03-02)

### Bug Fixes

- **ci**: Replace flaky just installation with setup-just action
  ([`bbb3b9c`](https://github.com/markhedleyjones/container-magic/commit/bbb3b9c7097b758d62629fbea427ce873b27a450))


## v1.12.4 (2026-03-02)

### Bug Fixes

- **templates**: Jinja2 force variable, Podman name filter, TTY detection
  ([`deca695`](https://github.com/markhedleyjones/container-magic/commit/deca69511afd0027645b570bda07b9448febf41a))

### Documentation

- Fix documentation gaps and inaccuracies
  ([`514aa1f`](https://github.com/markhedleyjones/container-magic/commit/514aa1f3e17c42c2b2c1c0106e927add89ea4844))


## v1.12.3 (2026-02-23)

### Bug Fixes

- User config validation, home path in run.sh, UID/GID 0, steps alias
  ([`b00f2dd`](https://github.com/markhedleyjones/container-magic/commit/b00f2dd122c8d06028c35f4739d130f915e840fa))


## v1.12.2 (2026-02-23)

### Bug Fixes

- **template**: Quote ENV values, expand instruction passthrough, validate copy args
  ([`7b0dbc2`](https://github.com/markhedleyjones/container-magic/commit/7b0dbc2517e6f0218b23f53123a69b1c416ef437))

### Chores

- Add CLAUDE.md to .gitignore
  ([`ee9488b`](https://github.com/markhedleyjones/container-magic/commit/ee9488bfb78f6cdb58778dbd571765cce31e5658))


## v1.12.1 (2026-02-23)

### Bug Fixes

- **template**: Emit workspace ARG/ENV in every stage, not just the first
  ([`ebae5d7`](https://github.com/markhedleyjones/container-magic/commit/ebae5d70861edccb1f69f863516389181b239896))


## v1.12.0 (2026-02-18)

### Features

- **runtime**: Add detached mode and fix X11 auth for Docker
  ([`61b47a1`](https://github.com/markhedleyjones/container-magic/commit/61b47a1eeee8227830f36fad14b7a17e4edb4446))

- **runtime**: Add IPC namespace sharing
  ([`9296e34`](https://github.com/markhedleyjones/container-magic/commit/9296e3471adc6fdc8cfa2c9651aaa013634a9d13))

- **runtime**: Add named containers to run scripts
  ([`bc96dda`](https://github.com/markhedleyjones/container-magic/commit/bc96ddae31bd610d388f007077af0b84e7514c17))


## v1.11.1 (2026-02-16)

### Bug Fixes

- Resolve base image chain for detection, fix Alpine adduser -G
  ([`966a810`](https://github.com/markhedleyjones/container-magic/commit/966a810f98c10fc45f7c8475ceedb76e428bb301))

### Testing

- Add build tests for Alpine, Debian, and Fedora base images
  ([`d3ee018`](https://github.com/markhedleyjones/container-magic/commit/d3ee018aca092d2600ab8408566c64b7c2f7ec80))


## v1.11.0 (2026-02-11)

### Continuous Integration

- Fix duplicate PyPI publish on release commits
  ([`0227b07`](https://github.com/markhedleyjones/container-magic/commit/0227b07b3c23fa0d5650290e20423de8595d8187))

### Documentation

- Remove stale auto_update example, add AWS credentials to features list
  ([`bdd61de`](https://github.com/markhedleyjones/container-magic/commit/bdd61de8536f7aa55fd3f4c13b8f2c451e6114a3))

### Features

- Explicit system package manager fields (apt, apk, dnf)
  ([`86ad39b`](https://github.com/markhedleyjones/container-magic/commit/86ad39b53f4d7c72460d31dbeabca0fbab4bfff0))


## v1.10.0 (2026-02-11)

### Features

- Default auto_update to true and add DO NOT EDIT warnings
  ([`2bfc015`](https://github.com/markhedleyjones/container-magic/commit/2bfc015ab1302fcbdd66c2f723976e38c39ebf51))


## v1.9.0 (2026-02-11)

### Continuous Integration

- Add GitHub Pages deployment for docs
  ([#15](https://github.com/markhedleyjones/container-magic/pull/15),
  [`3c0b858`](https://github.com/markhedleyjones/container-magic/commit/3c0b858a5de3d90621f94a5c90469b0ff63ad259))

- Skip PyPI publish when no release is created
  ([#14](https://github.com/markhedleyjones/container-magic/pull/14),
  [`29b2a41`](https://github.com/markhedleyjones/container-magic/commit/29b2a412b4984d0cfa90ff1cbf7a358fd83283a5))

### Documentation

- Add MkDocs Material documentation site
  ([#13](https://github.com/markhedleyjones/container-magic/pull/13),
  [`c6031c7`](https://github.com/markhedleyjones/container-magic/commit/c6031c79c8c8e6541e1958ed24e50eda7709fcb3))

- Fix incorrect config paths and wrong troubleshooting info in README
  ([#12](https://github.com/markhedleyjones/container-magic/pull/12),
  [`153128c`](https://github.com/markhedleyjones/container-magic/commit/153128ca9560117538d0800cf3fbf14915eabbb4))

### Features

- Add runtime.volumes and runtime.devices, rename network to network_mode
  ([`d9b8a0c`](https://github.com/markhedleyjones/container-magic/commit/d9b8a0c30917ee381960b728adf8dbcc30668c87))

- Wire features, volumes, and devices into run.sh and standalone scripts
  ([`8512c02`](https://github.com/markhedleyjones/container-magic/commit/8512c02f5a3ee4268b4c2bb721431e527de52fd7))


## v1.8.0 (2026-02-08)

### Features

- **steps**: Add user-aware copy steps and become_user/become_root aliases
  ([#11](https://github.com/markhedleyjones/container-magic/pull/11),
  [`dda2059`](https://github.com/markhedleyjones/container-magic/commit/dda20596cd03dd507520383ccb5beb4ba1e14a57))


## v1.7.0 (2026-02-08)

### Features

- **commands**: Add port publishing support
  ([#10](https://github.com/markhedleyjones/container-magic/pull/10),
  [`6fa6c02`](https://github.com/markhedleyjones/container-magic/commit/6fa6c024b93b418826245de02aa41733773c451a))


## v1.6.0 (2026-02-08)

### Continuous Integration

- Use RELEASE_TOKEN for semantic-release to bypass branch protection
  ([#9](https://github.com/markhedleyjones/container-magic/pull/9),
  [`9dc4727`](https://github.com/markhedleyjones/container-magic/commit/9dc47275837c4fb8b587d8c5829d962bda0787a3))

### Features

- **commands**: Add optional positional arguments support
  ([#8](https://github.com/markhedleyjones/container-magic/pull/8),
  [`a6a2d03`](https://github.com/markhedleyjones/container-magic/commit/a6a2d035f0407a22a0feafb589d1306b054aed31))


## v1.5.3 (2026-02-08)

### Bug Fixes

- Handle multi-line commands and argument substitution
  ([`57ac829`](https://github.com/markhedleyjones/container-magic/commit/57ac829bbfe91965ab506929a5cc7a9b965a6bcb))

- Podman compatibility (env isolation, X11 access, TTY flags)
  ([`7e56ddb`](https://github.com/markhedleyjones/container-magic/commit/7e56ddb18b910c428ae59ca90d9d9695c2b57aa1))


## v1.5.2 (2026-01-04)

### Bug Fixes

- Move TTY flags before image in Justfile run recipe
  ([#7](https://github.com/markhedleyjones/container-magic/pull/7),
  [`283d7af`](https://github.com/markhedleyjones/container-magic/commit/283d7af87cd58737c6a6bdf7633e79c6346fe025))


## v1.5.1 (2025-12-26)

### Bug Fixes

- Resolve CLI output buffering with os.execvp
  ([#6](https://github.com/markhedleyjones/container-magic/pull/6),
  [`a98c1ce`](https://github.com/markhedleyjones/container-magic/commit/a98c1ce8c53f28273e2ca601fff7639839d1d46a))


## v1.5.0 (2025-12-26)

### Features

- Add runtime.network configuration option
  ([#5](https://github.com/markhedleyjones/container-magic/pull/5),
  [`0454301`](https://github.com/markhedleyjones/container-magic/commit/04543011ab700952e850c0cfa68614c3449403b7))


## v1.4.0 (2025-12-25)

### Features

- Add container reuse to custom commands
  ([#4](https://github.com/markhedleyjones/container-magic/pull/4),
  [`64997e4`](https://github.com/markhedleyjones/container-magic/commit/64997e44f99486d79d2a7b244e9c5d13285fe75a))


## v1.3.0 (2025-12-25)

### Features

- Add smart TTY detection to all command templates
  ([#3](https://github.com/markhedleyjones/container-magic/pull/3),
  [`69bc2c2`](https://github.com/markhedleyjones/container-magic/commit/69bc2c276acd9caed7aa01b26d8377fb842ee30e))


## v1.2.0 (2025-12-16)

### Features

- Custom command improvements and runtime feature inheritance
  ([#2](https://github.com/markhedleyjones/container-magic/pull/2),
  [`708bee7`](https://github.com/markhedleyjones/container-magic/commit/708bee78643e96c436c190e02dece2ac1103ac42))


## v1.1.0 (2025-12-16)

### Bug Fixes

- Add \$WORKDIR variable and escape dollar signs in Justfile commands
  ([`cd4ffcb`](https://github.com/markhedleyjones/container-magic/commit/cd4ffcbc832981fffa3c1e30edb850bc3943f89f))

- Add blank lines in Dockerfile template for apk and dnf package managers
  ([`5c419d4`](https://github.com/markhedleyjones/container-magic/commit/5c419d4e7e9088834342d4dfe8ebe2eb7d70948e))

- Add workspace mount to custom command scripts
  ([`dd32fe2`](https://github.com/markhedleyjones/container-magic/commit/dd32fe2ac0c162c3b725b9c375b073a6d123a65c))

- Always set WORKSPACE environment variable unconditionally in base stage
  ([#1](https://github.com/markhedleyjones/container-magic/pull/1),
  [`8a23369`](https://github.com/markhedleyjones/container-magic/commit/8a233695e5e5ef39fc5b49fa16257f70aa1da70b))

- Automatically inject WORKSPACE environment variable for custom commands
  ([`493e215`](https://github.com/markhedleyjones/container-magic/commit/493e215c7f69895d08433fbb29d332b270007b08))

- Change default production_user from 'nonroot' to 'user'
  ([`0b45bf8`](https://github.com/markhedleyjones/container-magic/commit/0b45bf8cb675fa97cb3cc89d316c4d6027c3be95))

- Check image exists locally before executing commands
  ([`8b3e02f`](https://github.com/markhedleyjones/container-magic/commit/8b3e02ff4ec7ec1837effacdb9cfe306a07d846d))

- Check image exists locally before executing commands
  ([`ce2246f`](https://github.com/markhedleyjones/container-magic/commit/ce2246ff3711f81c5e24e3c9115869c870c5da64))

- Custom_command.j2: Escape double quotes in command for Justfile recipes
  ([`1cd8fcb`](https://github.com/markhedleyjones/container-magic/commit/1cd8fcb4c19c0c0db0dec25f560add594b4adf44))

- Dynamically set $WORKSPACE at container runtime
  ([`1392382`](https://github.com/markhedleyjones/container-magic/commit/13923820e6b9732d24bddfc215168d06ecb7c43c))

- Escape dollar signs in command strings for container expansion
  ([`beff5d2`](https://github.com/markhedleyjones/container-magic/commit/beff5d23cd71d8003964df13d0bafe9e837b4747))

- Escape quotes in run.sh commands with nested quotes
  ([`f8dee4b`](https://github.com/markhedleyjones/container-magic/commit/f8dee4b4d4a7791cef249334ce85840ebdc6c077))

- Only add create_user step and user args when user is explicitly configured
  ([`d5735bc`](https://github.com/markhedleyjones/container-magic/commit/d5735bcc0bb3cee7631aecd427b981e92d70c971))

- Only add TTY flags for interactive shell mode, not for command execution
  ([`8e4a9ac`](https://github.com/markhedleyjones/container-magic/commit/8e4a9ac3ced99f92814d0a539bf2937cb2115402))

- Properly handle command arguments in Justfile with set +u toggle
  ([`e8e8401`](https://github.com/markhedleyjones/container-magic/commit/e8e84017e3bf922fcdfd0f0e1e9b0f25715691a6))

- Provide default uid/gid (1000) when not specified in user config
  ([#1](https://github.com/markhedleyjones/container-magic/pull/1),
  [`8a23369`](https://github.com/markhedleyjones/container-magic/commit/8a233695e5e5ef39fc5b49fa16257f70aa1da70b))

- Remove --userns=keep-id from custom commands in podman
  ([`614cb2c`](https://github.com/markhedleyjones/container-magic/commit/614cb2c38138274d5faf8635a057411206699419))

- Remove interactive mode from custom commands
  ([`07b07ab`](https://github.com/markhedleyjones/container-magic/commit/07b07ab95b156c263672921ada6733a62ded68c7))

- Set WORKSPACE environment variable unconditionally in base stage
  ([`c525fc7`](https://github.com/markhedleyjones/container-magic/commit/c525fc7c591458c54fff66f6cb7657981a8e768b))

- Use container home directory for custom command volume mounts
  ([`4dce874`](https://github.com/markhedleyjones/container-magic/commit/4dce874fd200c16b796179ce43b4e438c754dd75))

- Use container_home for workdir in main run recipe
  ([`60d05da`](https://github.com/markhedleyjones/container-magic/commit/60d05da0a507923a66d48d9bb9dc9e07c267302e))

- Use container_home for workspace and AWS mounts in main run recipe
  ([`9a51bc8`](https://github.com/markhedleyjones/container-magic/commit/9a51bc884382ecc1558d2cba8d854e50e8a6a8e6))

- Use dynamic ENV variables for WORKSPACE path to work with host user mode
  ([#1](https://github.com/markhedleyjones/container-magic/pull/1),
  [`8a23369`](https://github.com/markhedleyjones/container-magic/commit/8a233695e5e5ef39fc5b49fa16257f70aa1da70b))

- Use hardcoded paths for WORKDIR and WORKSPACE environment variables
  ([`0e2ff7f`](https://github.com/markhedleyjones/container-magic/commit/0e2ff7f35d61cfc07fef62a1cc1eb80e860511d8))

- Use Optional[] for Python 3.9 compatibility
  ([#1](https://github.com/markhedleyjones/container-magic/pull/1),
  [`8a23369`](https://github.com/markhedleyjones/container-magic/commit/8a233695e5e5ef39fc5b49fa16257f70aa1da70b))

- Use positional parameters for command execution to avoid quoting issues
  ([`1162543`](https://github.com/markhedleyjones/container-magic/commit/1162543f494cba78cadfa82c44255d746d13d0c6))

### Continuous Integration

- Install just for integration tests
  ([#1](https://github.com/markhedleyjones/container-magic/pull/1),
  [`8a23369`](https://github.com/markhedleyjones/container-magic/commit/8a233695e5e5ef39fc5b49fa16257f70aa1da70b))

### Documentation

- Add comprehensive Build Steps Reference section to README
  ([`9fe518f`](https://github.com/markhedleyjones/container-magic/commit/9fe518f959fa411fb3d465966cbdfc7385dc9de5))

- Add comprehensive guide for downloading and caching assets
  ([`92eb1aa`](https://github.com/markhedleyjones/container-magic/commit/92eb1aafffb8070e01526894df41efa0e5334ed0))

- Add PEP 668 guidance for pip on Debian/Ubuntu
  ([`30fea34`](https://github.com/markhedleyjones/container-magic/commit/30fea34268eeec9c0cc91277a39174c7d46fd50a))

- Add user handling section explaining dev vs prod behavior
  ([`621ac7c`](https://github.com/markhedleyjones/container-magic/commit/621ac7c177e5ed1224430486b8f3744d6d9ae189))

- Clarify $WORKSPACE environment variable usage
  ([`d09813e`](https://github.com/markhedleyjones/container-magic/commit/d09813e94d50895731a625cac858741cceeaf433))

- Clarify create_user defaults and copy_workspace chown behaviour
  ([`70ca530`](https://github.com/markhedleyjones/container-magic/commit/70ca530647d6544ed358b29b4659544421c8c23d))

- Clarify that copy_cached_assets must be explicitly added to steps and chown is automatic
  ([`f328869`](https://github.com/markhedleyjones/container-magic/commit/f3288694b7d539b0338024c7cba57a5f979cbbbb))

- Consolidate cached assets documentation to reduce duplication
  ([`50fe2a5`](https://github.com/markhedleyjones/container-magic/commit/50fe2a5cfd55403a5a0e072e090cac8a1262da71))

- Enhance README with larger artwork and status badges
  ([`c74fa52`](https://github.com/markhedleyjones/container-magic/commit/c74fa52b730bfa0e44de36f94cb693814dc1de1d))

- Use 'user' instead of 'appuser' in examples
  ([`aec173d`](https://github.com/markhedleyjones/container-magic/commit/aec173d678006bc3bb0010f40e69d00cfe0654b2))

### Features

- Per-stage user configuration ([#1](https://github.com/markhedleyjones/container-magic/pull/1),
  [`8a23369`](https://github.com/markhedleyjones/container-magic/commit/8a233695e5e5ef39fc5b49fa16257f70aa1da70b))

### Refactoring

- Move workspace setup to base stage only
  ([`2f28cbe`](https://github.com/markhedleyjones/container-magic/commit/2f28cbe8b1cc6418045ec65f78905328f7c70bad))

- Simplify WORKDIR setup to use user_home directly, remove confusing workspace_home variable
  ([#1](https://github.com/markhedleyjones/container-magic/pull/1),
  [`8a23369`](https://github.com/markhedleyjones/container-magic/commit/8a233695e5e5ef39fc5b49fa16257f70aa1da70b))

- Update generators to use new user config structure
  ([#1](https://github.com/markhedleyjones/container-magic/pull/1),
  [`8a23369`](https://github.com/markhedleyjones/container-magic/commit/8a233695e5e5ef39fc5b49fa16257f70aa1da70b))

- User configuration schema - top-level user section with per-target config
  ([#1](https://github.com/markhedleyjones/container-magic/pull/1),
  [`8a23369`](https://github.com/markhedleyjones/container-magic/commit/8a233695e5e5ef39fc5b49fa16257f70aa1da70b))

### Testing

- Add case for user defined but not used in create/switch steps
  ([`8cbb62f`](https://github.com/markhedleyjones/container-magic/commit/8cbb62f1d4a47ee70787d73a8f6575315b88ddcc))

- Add comprehensive user config default tests
  ([`26c6eab`](https://github.com/markhedleyjones/container-magic/commit/26c6eab7fb89d4d5efb8a2d35ae1f37ad996368a))

- Add integration tests for package installation across base images
  ([`5ba4fe9`](https://github.com/markhedleyjones/container-magic/commit/5ba4fe917eab3534e5af08636fe23b1cbc53c67b))

- Add quote escaping test for Justfile custom commands
  ([`7fcde62`](https://github.com/markhedleyjones/container-magic/commit/7fcde62be4142b2660abdcd7e80c630bc3b455d6))

- Add regression test for WORKSPACE environment variable
  ([`2f62eb0`](https://github.com/markhedleyjones/container-magic/commit/2f62eb0e6cafa85444af3c024768d0f37c483ec6))

- Add ROS1 integration test for workspace mounting and project initialization
  ([#1](https://github.com/markhedleyjones/container-magic/pull/1),
  [`8a23369`](https://github.com/markhedleyjones/container-magic/commit/8a233695e5e5ef39fc5b49fa16257f70aa1da70b))

- Add Ubuntu 24.04 package installation test
  ([`0e535f7`](https://github.com/markhedleyjones/container-magic/commit/0e535f7c919f1280703eb7a4ea41e957542d71a8))

- Fix workspace_env tests to properly escape variables and use printenv
  ([#1](https://github.com/markhedleyjones/container-magic/pull/1),
  [`8a23369`](https://github.com/markhedleyjones/container-magic/commit/8a233695e5e5ef39fc5b49fa16257f70aa1da70b))

- Update test_user_validation.py to use new user config format
  ([#1](https://github.com/markhedleyjones/container-magic/pull/1),
  [`8a23369`](https://github.com/markhedleyjones/container-magic/commit/8a233695e5e5ef39fc5b49fa16257f70aa1da70b))


## v1.0.0 (2025-11-24)

- Initial Release
