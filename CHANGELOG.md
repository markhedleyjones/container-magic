# CHANGELOG

<!-- version list -->

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
