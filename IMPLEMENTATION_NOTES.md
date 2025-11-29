# User Configuration Refactor - Implementation Notes

**Branch:** feature/user-config-refactor
**Status:** Schema complete, generators & templates pending
**Token-conscious handoff:** Documentation updated for fresh session continuation

## What Was Done This Session

### 1. Configuration Schema Refactor ✅
**File:** `src/container_magic/core/config.py`

**Changes:**
- Removed: `ProjectConfig.user`, `ProjectConfig.production_user`, `ProjectConfig.development_user`
- Added: Top-level `UserConfig` class with `development` and `production` fields
- Added: `UserTargetConfig` class for individual target configuration
- Added: Validators for `host` field:
  - Rejects `host: false` (must be true or omitted)
  - Rejects `host: true` combined with name/uid/gid (mutually exclusive)

**New Config Structure:**
```yaml
user:
  development:
    host: true                    # Use actual host user at build time
  production:
    name: user
    uid: 1000
    gid: 1000
```

### 2. Test Fixtures Updated ✅
**Files:** All 6 files in `tests/fixtures/configs/`

All updated from old `project.production_user` to new top-level `user.production` format.

**Verified:** `pytest tests/unit/test_config.py` - All 8 tests PASS ✅

### 3. Documentation Updated ✅
- `GOAL.md` - Added implementation status and next-session quickstart
- `CONFIGURATION_SCENARIOS.md` - Updated to reflect implemented schema
- `IMPLEMENTATION_NOTES.md` - This file

## What Still Needs to Be Done

### Priority 1: Generators (5 files)
1. `dockerfile.py` - Complete per-target user resolution in `generate_dockerfile()`
2. `justfile.py` - Handle `host: true` flag, pass host user build args
3. `build_script.py` - Extract production user config and pass to template
4. `run_script.py` - Use production user config for WORKDIR/run args
5. `standalone_commands.py` - Use production user config for workdir

**Key insight:** Each generator needs to:
- Look up `config.user.<target>` for their respective target
- Pass user values as build args (`--build-arg USER_UID=...`, etc.)
- If `host: true`, use `$(id -u)`, `$(id -g)`, `$(id -u -n)`, `$(echo ~)`

### Priority 2: Templates (4 files)
1. `Dockerfile.j2` - Add user creation/renaming logic:
   - Check if uid/gid exist in base image
   - Rename if needed (ubuntu→ros use case)
   - Debian: `usermod -l newname oldname`
   - Alpine: `deluser oldname && adduser -u uid -G gid newname`
   - Skip creation if exact match

2. `Justfile.j2`, `build.sh.j2`, `run.sh.j2` - Conditional user args

### Priority 3: Tests
- `test_user_validation.py` - 21 tests need rewriting for new config format
- Integration tests - Update config references

### Priority 4: CLI & Docs
- `main.py` - Update `cm init` templates to new format
- `README.md` - Update examples

## Recommended Next Steps

1. **Start fresh session on the branch**
2. **Run tests to see failures:**
   ```bash
   pytest tests/unit/test_user_validation.py -x
   ```
3. **Update generators in order** (dockerfile → justfile → build_script)
4. **Update templates** with user creation/renaming logic
5. **Rewrite tests** to match new config
6. **Run full test suite** and fix failures

## Key Code References

**New Schema:**
- `UserTargetConfig` - lines 40-72 in config.py
- `UserConfig` - lines 75-83 in config.py
- Validators - `validate_host_field()` and `validate_host_exclusive()`

**Generator Start:**
- `get_user_config(config, target)` - lines 18-27 in dockerfile.py (updated signature)

**Fixtures:**
- All 6 YAML files in `tests/fixtures/configs/` updated and working

## Testing Strategy

**Scenarios to validate:**
1. No user config → both targets run as root
2. Production user only → dev=root, prod=fixed user
3. Development host + production fixed → dev=your user, prod=stable
4. ROS1 scenario → ubuntu user renamed to configured name

**Config that works now:**
```yaml
user:
  production:
    name: user
    uid: 1000
```

**Config in development:**
```yaml
user:
  development:
    host: true
  production:
    name: user
    uid: 1000
```

All fixtures and schema are ready. Just need to wire the generators and templates through.
