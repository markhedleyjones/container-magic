# Configuration Scenarios for User Management

## STATUS: Configuration Schema COMPLETED ✅

**Implementation Progress:**
- ✅ Schema changes (config.py) - DONE
- ✅ Fixture files updated - DONE
- ✅ Config validation tests passing - DONE
- ⏳ Generators (dockerfile, justfile, build_script, etc.) - TODO in next session
- ⏳ Templates (Dockerfile.j2, Justfile.j2, etc.) - TODO in next session
- ⏳ Full test suite - TODO in next session

## IMPLEMENTED MODEL (feature/user-config-refactor branch)

**Key principles:**
- **Top-level `user` section**: Separate from `project` config, organized by target (development, production)
- **Target-specific configuration**: Define different users for development vs production
- **Default to root**: If user not specified for a target, it defaults to root (no user creation)
- **`host: true` key**: Capture actual host user (UID/GID/name) at build time for development
- **Configuration is truth**: If base image has a conflicting user, rename it to match config
- **Validation**:
  - `host: true` cannot be combined with `name`, `uid`, or `gid`
  - `host: false` is explicitly rejected (use omitted instead)
  - If `host` omitted, must specify `name`, `uid`, `gid` or user config is ignored

---

## STANDARD SCENARIOS

### Scenario 1: No User Configuration (Everything runs as root)
```yaml
project:
  name: simple-container
  workspace: workspace

# user: section completely omitted

stages:
  base:
    from: python:3.11-slim
```

**Expected behaviour:**
- **Development**: Runs as root (uid=0)
  - No `user` section defined
  - No user creation in image
  - No build args for user

- **Production**: Runs as root (uid=0)
  - No `user` section defined
  - No user creation in image
  - No build args for user

- **Use case**: Quick prototyping, CI/CD pipelines, or when root is acceptable
- **Result**: ✓ Simplest possible configuration, no user management needed

---

### Scenario 2: Default Configuration (Recommended for Production)
```yaml
project:
  name: production-app
  workspace: workspace

user:
  development:
    host: true         # Use your actual host user
  production:
    name: user
    uid: 1000
    gid: 1000

stages:
  base:
    from: python:3.11-slim
    steps:
      - create_user     # Always created with values from target (development or production)

  production:
    from: base
    steps:
      - copy_workspace
```

**Expected behaviour:**
- **Base stage**: Always creates a user with build args
  - Build args determined by which target is being built

- **Development build** (justfile):
  - Passes host user args: `USER_UID=$(id -u)`, `USER_GID=$(id -g)`, `USER_NAME=$(id -u -n)`, `USER_HOME=$(echo ~)`
  - Base creates user with YOUR actual UID/GID/name
  - Files you create are owned by you

- **Production build** (build.sh):
  - Passes fixed args: `USER_UID=1000`, `USER_GID=1000`, `USER_NAME=user`, `USER_HOME=/home/user`
  - Base creates user 'user' with stable values
  - Reproducible across all deployments

- **Use case**: Production deployments with non-root user, development with your actual user
- **Result**: ✓ Secure production, convenient development (files owned by you)

---

### Scenario 3: Multi-Stage Build with Per-Target Users
```yaml
project:
  name: multi-stage-app
  workspace: workspace

user:
  development:
    host: true        # Dev uses your actual user
  production:
    name: user
    uid: 1000
    gid: 1000

stages:
  base:
    from: ubuntu:24.04
    steps:
      - install_system_packages
      - create_user     # Receives USER_* build args from whichever target is built

  development:
    from: base
    # Base has YOUR user (from development host:true)

  production:
    from: base
    steps:
      - copy_workspace  # Base has 'user' with uid=1000
```

**Expected behaviour:**
- **Base stage**: Always creates a user, but with different values per target

- **Development build** (justfile):
  - Passes `USER_UID=$(id -u)`, `USER_GID=$(id -g)`, `USER_NAME=$(id -u -n)`, `USER_HOME=$(echo ~)`
  - Base creates user with YOUR values
  - Image contains your user

- **Production build** (build.sh):
  - Passes `USER_UID=1000`, `USER_GID=1000`, `USER_NAME=user`, `USER_HOME=/home/user`
  - Base creates user 'user' with stable values
  - Image contains 'user' user

- **Use case**: Most common real-world scenario - convenient development, stable production
- **Result**: ✓ Same base stage code, different users per target via build args

---

### Scenario 4: Advanced - ROS1 Development (user renaming)
```yaml
project:
  name: ros-development
  workspace: workspace

user:
  development:
    host: true        # Always use your actual user
  production:
    name: ros
    uid: 1000
    gid: 1000

stages:
  base:
    from: osrf/ros:melodic-desktop  # Has 'ubuntu' user with uid=1000
    steps:
      - create_user   # Will detect conflict and rename 'ubuntu' → 'ros'

  development:
    from: base

  production:
    from: base
    steps:
      - copy_workspace
```

**Expected behaviour:**
- **Base stage user creation**:
  - ROS image has 'ubuntu' user with uid=1000
  - Config specifies different name 'ros' with same uid=1000
  - Conflict detected → **rename** existing user
  - `usermod -l ros ubuntu` (Debian/Ubuntu syntax)
  - After rename, user 'ros' exists with uid=1000

- **Development build** (justfile):
  - Passes `USER_UID=$(id -u)`, `USER_GID=$(id -g)`, `USER_NAME=$(id -u -n)`, etc.
  - Base recreates user in image with YOUR actual values
  - Even though base originally had 'ros' user, dev gets your user instead
  - Files in workspace owned by your UID/GID

- **Production build** (build.sh):
  - Passes `USER_UID=1000`, `USER_GID=1000`, `USER_NAME=ros`, etc.
  - Base recreates 'ros' user (or skips if exact match from renaming)
  - Stable and reproducible

- **Use case**: ROS1 robotics - solves the ubuntu→ros renaming problem elegantly
- **Result**: ✓ Configuration is truth - base image users adapt to your config

---

## TESTING MATRIX

| Scenario | Use Case | Dev Behaviour | Prod Behaviour | Key Feature |
|----------|----------|---------------|----------------|-------------|
| 1 | Simple container | root (uid=0) | root (uid=0) | No user config - simplest |
| 2 | Production-grade app | your actual user | uid=1000:user stable | **Recommended default** |
| 3 | Multi-stage complex | your actual user | uid=1000:user stable | Per-target user via build args |
| 4 | ROS1 development | your actual user | uid=1000:ros stable | **Renames base image user** |

---

## Implementation Checklist

### Configuration Schema Changes
- [ ] Remove `user`, `production_user`, `development_user` from `ProjectConfig`
- [ ] Create new top-level `UserConfig` section (separate from project)
- [ ] Structure: `user: { development?, production? }`
  - [ ] development comes first (primary workflow)
  - [ ] production comes second (deployed version)
- [ ] Fields per target: `name`, `uid`, `gid`, `home` (optional), `host` (true/false)
- [ ] Default behaviour: if target not specified, defaults to root (no user directive)

### Dockerfile Generation - `create_user` Step (always in base stage)
- [ ] Always include `create_user` in base stage (not conditional per-target)
- [ ] Accept user config as build arguments: `USER_UID`, `USER_GID`, `USER_NAME`, `USER_HOME`
- [ ] Before creating user, check if uid/gid already exist:
  - [ ] If exact match (name + uid + gid): skip creation
  - [ ] If uid exists with different name: **rename** existing user to configured name
  - [ ] If neither: create new user with specified values

### User Renaming Implementation
- [ ] Detect base image distro (Alpine, Debian, etc.)
- [ ] Debian/Ubuntu: `usermod -l newname oldname`
- [ ] Alpine: `deluser oldname && adduser -u {uid} -G {gid} newname`
- [ ] Handle both cases in generated Dockerfile template

### Build Script Generation - Pass target-specific user args
- [ ] **Justfile (development build)**:
  - [ ] Look up `user.development` config
  - [ ] If `host: true`: pass `--build-arg USER_UID=$(id -u) --build-arg USER_GID=$(id -g) --build-arg USER_NAME=$(id -u -n) --build-arg USER_HOME=$(echo ~)`
  - [ ] Otherwise: pass `--build-arg USER_UID={uid} --build-arg USER_GID={gid} --build-arg USER_NAME={name} --build-arg USER_HOME={home}`
  - [ ] If not specified: pass no user args (runs as root in container)

- [ ] **build.sh (production build)**:
  - [ ] Look up `user.production` config
  - [ ] Pass `--build-arg USER_UID={uid} --build-arg USER_GID={gid} --build-arg USER_NAME={name} --build-arg USER_HOME={home}`
  - [ ] If not specified: pass no user args (runs as root in container)

### Testing
- [ ] Scenario 1: No user config (both dev and prod run as root)
- [ ] Scenario 2: Default configuration (dev=host user, prod=stable user)
- [ ] Scenario 3: Multi-stage (same base stage code, different users per target)
- [ ] Scenario 4: ROS1 (host dev, prod=ros with ubuntu→ros renaming)
  - [ ] User renaming on Debian/Ubuntu
  - [ ] User renaming on Alpine
  - [ ] Verify development gets host user despite base image renaming

### Documentation
- [ ] Update README with top-level `user` section structure
- [ ] Show `development` comes before `production` in examples
- [ ] Document `host: true` key for development
- [ ] Document per-target user definitions
- [ ] Document per-target defaults (defaults to root)
- [ ] Add examples for all 4 scenarios
- [ ] Update init templates to generate default config with dev host:true

