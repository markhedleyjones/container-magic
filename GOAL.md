# Container Magic User Management Configuration

## Objective

Consolidate user management into a single, consistent approach that works everywhere:
- **One config field** (`production_user`) instead of `user`, `production_user`, `development_user`
- **Development always uses host user** (captured at build time via `id`)
- **Production uses configured user** with stable, reproducible UID/GID
- **Handle base image users** gracefully when UID/GID conflicts occur

## Design Decisions

1. **User config becomes top-level, target-specific**
   - Move user configuration out of `project` section
   - Create top-level `user` section with target-specific configs (development, production, etc.)
   - Makes it immediately clear that user config relates to build targets
   - User is defined per-target (development, production), not per-stage

2. **User is always created in base stage**
   - `create_user` step goes in base stage (not conditional per-target)
   - Base stage receives user config as build arguments
   - Different targets build with different user values (via `--build-arg`)
   - Example config (development first):
     ```yaml
     user:
       development:
         host: true    # Use actual host user (UID/GID/name captured at build)
       production:
         name: user
         uid: 1000
         gid: 1000
     ```

3. **Target-specific user selection**
   - When building **development** target:
     - Justfile passes: `USER_UID=$(id -u)`, `USER_GID=$(id -g)`, `USER_NAME=$(id -u -n)`, `USER_HOME=$(echo ~)`
     - Base stage creates user with YOUR actual values
   - When building **production** target:
     - build.sh passes: `USER_UID=1000`, `USER_GID=1000`, `USER_NAME=user`, `USER_HOME=/home/user`
     - Base stage creates user with those fixed values
   - Same `create_user` step in base, different values per target

4. **Special `host` key for host user**
   - When `host: true` is set for a target:
     - Signals "capture actual host user at build time"
     - Justfile uses `$(id -u)`, `$(id -g)`, etc. as build args
     - Only makes sense for development (production should always be stable)

5. **Handle pre-existing users: configuration is truth**
   - Before creating a user, check if UID/GID already exist in base image
   - If user exists with different name (e.g., ubuntu user with uid=1000, but we want name=ros):
     - **Rename existing user** to match our configuration
     - Configuration becomes the source of truth
   - If user exists with exact match (name + uid + gid): skip creation
   - This solves ROS image problem: ubuntu user gets renamed to whatever config specifies

## Implementation Plan

1. **Configuration Schema**
   - Create top-level `user` section (separate from `project`)
   - Structure:
     ```yaml
     user:
       development:  # optional
         host: true  # special key: use actual host user
       production:   # optional (default: root if not specified)
         name: user
         uid: 1000
         gid: 1000
     ```
   - Fields per target: `name`, `uid`, `gid`, `home` (optional), `host` (boolean, optional)
   - **Validation for `host` field:**
     - `host` can only be `true` or omitted
     - `host: false` is invalid and must error with clear message
     - Rationale: `host: false` is ambiguous (don't use host user, but no name/uid/gid specified)
     - If user wants fixed uid/gid, omit `host` and specify `name`, `uid`, `gid` instead
   - If `host: true`: capture host UID/GID/name at build time
   - If target not specified: no user created (runs as root)
   - home defaults to `/home/{name}` if not specified

2. **Dockerfile Generation - create_user Step (in base stage)**
   - Always include `create_user` step in base stage (not conditional)
   - Pass user config as build arguments: `USER_UID`, `USER_GID`, `USER_NAME`, `USER_HOME`
   - Check if any user with the desired uid/gid already exists
   - **If exact match** (same name + uid + gid): skip creation
   - **If UID taken by different user**: rename existing user to configured name
     - Debian: `usermod -l newname oldname`
     - Alpine: `deluser oldname && adduser -u uid -G name newname`
   - **If neither**: create new user with specified values
   - Build args used throughout base stage and inherited by all derived stages

3. **Build Script Generation - User Args**
   - **Justfile (development build)**:
     - Look up `user.development` config
     - If `host: true`: pass host user args `USER_UID=$(id -u)`, `USER_GID=$(id -g)`, `USER_NAME=$(id -u -n)`, `USER_HOME=$(echo ~)`
     - If not: use configured name/uid/gid (same as production)
     - If not specified: use root (no user creation)
   - **build.sh (production build)**:
     - Look up `user.production` config
     - Pass configured uid/gid/name values (always stable, never `host`)
     - If not specified: use root (no user creation)

4. **Testing & Documentation**
   - Scenario 1: No user config (both run as root)
   - Scenario 2: Production user only (dev=root, prod=user)
   - Scenario 3: Multi-stage different users (development=host, production=configured)
   - Scenario 4: ROS1 (ubuntu user renamed to ros, development=host)
   - Test user renaming: ubuntu→ros conversion on Debian/Alpine
   - Test per-target user resolution
   - Document host key and per-target configuration

## Implementation Status

### ✅ COMPLETED (on feature/user-config-refactor branch)

1. **Configuration Schema** (`src/container_magic/core/config.py`)
   - Removed `user`, `production_user`, `development_user` from `ProjectConfig`
   - Created new `UserTargetConfig` class with fields: `name`, `uid`, `gid`, `home`, `host` (optional boolean)
   - Created new `UserConfig` class with `development` and `production` targets
   - Added to `ContainerMagicConfig`: `user: Optional[UserConfig]`
   - Validators added:
     - `validate_host_field()` - rejects `host: false`, only accepts `host: true` or omitted
     - `validate_host_exclusive()` - rejects `host: true` combined with name/uid/gid
   - Updated comments helper method to reference new user section
   - **Removed** old `validate_user_config()` validator (no longer needed)

2. **All Test Fixtures Updated** (6 files in `tests/fixtures/configs/`)
   - minimal.yaml
   - with_custom_commands.yaml
   - with_env_vars.yaml
   - with_gpu_features.yaml
   - with_cached_assets.yaml
   - with_custom_stage.yaml

   All updated from old format:
   ```yaml
   project:
     production_user:
       name: appuser
   ```

   To new format:
   ```yaml
   user:
     production:
       name: appuser
   ```

3. **Unit Tests Status**
   - `tests/unit/test_config.py` - All 8 tests PASS ✅ (no changes needed)
   - Config loading and validation works with new schema

4. **Initial Generator Updates** (`src/container_magic/generators/dockerfile.py`)
   - Updated `get_user_config(config, target="production")` to:
     - Accept target parameter ("development" or "production")
     - Return `UserTargetConfig | None` for specified target
     - Works with new top-level `config.user` structure

### ❌ REMAINING WORK

**Generators** (need per-target user resolution):
- [ ] `dockerfile.py` - Complete `generate_dockerfile()` to pass target through pipeline
- [ ] `justfile.py` - Handle `host: true` flag, pass host user args to build
- [ ] `build_script.py` - Use `config.user.production` for build args
- [ ] `run_script.py` - Use `config.user.production` for workdir/run args
- [ ] `standalone_commands.py` - Use `config.user.production` for workdir

**Templates** (need user renaming logic):
- [ ] `Dockerfile.j2` - Add logic to:
  - Detect base image distro (Alpine vs Debian)
  - Check if uid/gid exist before creating user
  - Rename existing user if name mismatch (e.g., ubuntu→ros)
  - Skip creation if exact match found
- [ ] `Justfile.j2` - Make user args conditional based on development config
- [ ] `build.sh.j2` - Use config values instead of hardcoded 1000
- [ ] `run.sh.j2` - Update WORKDIR logic

**Tests** (mostly need rewriting):
- [ ] `test_user_validation.py` - Rewrite all 21 tests for new config format
- [ ] `test_config.py` - Add tests for new `user` section
- [ ] Integration tests - Update config references

**CLI & Docs**:
- [ ] `main.py` - Update init templates to new user config format
- [ ] `README.md` - Update examples to show new user structure

### Key Implementation Notes for Next Session

1. **Per-Target User Resolution Flow**:
   - Development target → `config.user.development`
     - If `host: true` → pass `USER_UID=$(id -u)`, `USER_GID=$(id -g)`, `USER_NAME=$(id -u -n)`, `USER_HOME=$(echo ~)`
     - If fixed values → pass `USER_UID={uid}`, `USER_GID={gid}`, etc.
     - If not defined → pass no user args (runs as root)
   - Production target → `config.user.production`
     - Always pass fixed values, never `host`
     - If not defined → pass no user args (runs as root)

2. **User Renaming in Dockerfile** (most complex):
   - Before creating user, detect if uid/gid already exist
   - Debian/Ubuntu: `usermod -l newname oldname`
   - Alpine: `deluser oldname && adduser -u {uid} -G {name} newname`
   - Skip creation if exact match (name + uid + gid already exists)

3. **Validation Rules Implemented**:
   - `host: true` cannot be combined with name/uid/gid
   - `host: false` is explicitly rejected with helpful error message
   - If `host` is omitted, name/uid/gid are used (or error if all missing)

4. **Testing Strategy**:
   - Scenario 1: No user config (both dev/prod run as root)
   - Scenario 2: Production user only (dev=root, prod=fixed)
   - Scenario 3: Development host + production fixed (most common)
   - Scenario 4: ROS1 with user renaming (ubuntu→ros)

### Files Modified This Session

1. `/home/mark/repos/container-magic/GOAL.md` - Added validation rules, updated status
2. `/home/mark/repos/container-magic/src/container_magic/core/config.py` - Complete rewrite of user config classes
3. `/home/mark/repos/container-magic/tests/fixtures/configs/minimal.yaml` - Updated format
4. `/home/mark/repos/container-magic/tests/fixtures/configs/with_custom_commands.yaml` - Updated format
5. `/home/mark/repos/container-magic/tests/fixtures/configs/with_env_vars.yaml` - Updated format
6. `/home/mark/repos/container-magic/tests/fixtures/configs/with_gpu_features.yaml` - Updated format
7. `/home/mark/repos/container-magic/tests/fixtures/configs/with_cached_assets.yaml` - Updated format
8. `/home/mark/repos/container-magic/tests/fixtures/configs/with_custom_stage.yaml` - Updated format
9. `/home/mark/repos/container-magic/src/container_magic/generators/dockerfile.py` - Updated `get_user_config()` signature

### Next Session Quickstart

When resuming on the new branch:
1. Run `pytest tests/unit/test_config.py` to confirm config changes work ✅
2. Run `pytest tests/unit/test_user_validation.py` to see what needs rewriting
3. Update generators in order: dockerfile → justfile → build_script → run_script → standalone_commands
4. Update templates with new logic
5. Rewrite tests
6. Run full test suite

The config schema is solid and validated. All the remaining work is wiring it through the generators and templates.
