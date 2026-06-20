# Publish Infrastructure

Publish artifacts to Artifactory, Nexus, or Gitea package registries
(Maven/PyPI), and OCI container images to a Docker registry. A single
`mint` invocation handles version resolution, tagging, and pushes to
both registry types in a coordinated run.

## Quick Start

```bash
# 1. Configure registries in .bazelrc or user.bazelrc (one-time)
#    build:publish --//tools/publish:url=https://registry.invalid/artifactory
#    build:publish --//tools/publish:platform=artifactory
#    build:publish --//tools/publish:docker_url=https://registry.invalid

# 2. Publish all modules (dev version) — both Maven/PyPI artifacts and OCI images
bazel run //tools/publish:mint -- --mode dev --include-pub-targets all

# 3. Publish a release
bazel run //tools/publish:mint -- --mode release --branch main --include-pub-targets all
```

## mint — Publish Orchestrator

`mint` is the primary interface for publishing. It manages version resolution
via git tags and `.publish.toml`, then invokes each module's `:publish` and
`:publish_image` targets with the correct `PUBLISH_VERSION` and `PUBLISH_MODE`.
Per-module ordering is deterministic: artifact track first, image track second;
first failure aborts the run.

### CLI Usage

```bash
# Dev — everything (artifact + image), from working tree
bazel run //tools/publish:mint -- --mode dev --include-pub-targets all

# Dev — Maven/PyPI artifacts only
bazel run //tools/publish:mint -- --mode dev --include-pub-targets artifacts

# Dev — OCI images only
bazel run //tools/publish:mint -- --mode dev --include-pub-targets images

# Dev — single component set, both tracks
bazel run //tools/publish:mint -- --mode dev --scope java_all --include-pub-targets all

# Dev — single module
bazel run //tools/publish:mint -- --mode dev --scope //modules/java_lib --include-pub-targets all

# Release — everything, from clean worktree
bazel run //tools/publish:mint -- --mode release --branch main --include-pub-targets all

# Release — component set with version override
bazel run //tools/publish:mint -- --mode release --branch main --scope java_all --version 2.0.0 --include-pub-targets all

# Dry run — print resolved plan without building or publishing
bazel run //tools/publish:mint -- --mode dev --include-pub-targets all --dry-run
```

### CLI Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--mode` | Yes | `dev` (working tree) or `release` (worktree + tagging) |
| `--include-pub-targets` | Yes | `artifacts` (Maven/PyPI `:publish` only), `images` (OCI `:publish_image` only), or `all` (both, artifact-first per module). Mandatory — both registries have non-trivial blast radius and different audit trails, so the choice is explicit on every invocation. |
| `--scope` | No | Component set name, Bazel label (`//...`), or omit for everything |
| `--branch` | Release only | Branch to release from (e.g., `main`) |
| `--version` | No | Explicit version override (skips git tag resolution) |
| `--dry-run` | No | Print plan without executing |

### How It Works

1. **Resolve scope** — maps `--scope` to a list of module labels
2. **Group by version scope** — repo-wide, component set, or independent
3. **Resolve version** — queries git tags, applies schema (semver/calver/gitdate)
4. **Discover targets** — for each module, `bazel query` checks whether `:publish_image` exists. Libraries and binary kinds without a configured `[image_bases]` entry simply fall through.
5. **Execute** — for each module, runs the artifact track (`:publish`) first, then the image track (`:publish_image`) if discovered. Both invocations carry `PUBLISH_VERSION` and `PUBLISH_MODE`. `--include-pub-targets` selects which track(s) to invoke.

In release mode, mint additionally:
- Validates the branch exists on the remote
- Creates a secure worktree at the branch tip
- Tags locally before building
- Pushes tags only after all publishes succeed
- Cleans up tags and worktree on failure

## Version Configuration (`.publish.toml`)

Version schemas and component grouping are configured in `.publish.toml` at the repo root.

### Version Schemas

```toml
[repo]
schema = "{semver}"        # which schema to use (template substitution)

[schemas.semver]
release = "{major}.{minor}.{patch}"
development = "{next_version}.dev{git_count}+{git_commit}"
auto_increment = "patch"   # patch | minor | major

[schemas.calver]
release = "{YYYY}.{MM}.{DD}"
development = "{next_version}.dev{git_count}+{git_commit}"

[schemas.gitdate]
release = "{YYYY}.{MM}.{DD}.{git_count}"
development = "{next_version}+{git_commit}"
```

Custom schemas can be added by defining new `[schemas.<name>]` sections.

For inspiration on versioning schemes, see:
https://nesbitt.io/2024/06/24/from-zerover-to-semver-a-comprehensive-list-of-versioning-schemes-in-open-source.html

### Image Bases

`:publish_image` rules are emitted only for binary kinds with a
configured base. The `[image_bases]` table maps each kind to a Bazel
label resolving to an `oci_pull`-ed base image. A kind absent from the
table emits a warning at `publish_gen` time and skips `:publish_image`
for that package; the artifact `:publish` target is unaffected.

```toml
[conventions]
image_app_prefix = "app"  # in-image filesystem prefix; default "app"

[image_bases]
java_binary = "@gcr_io_distroless_java17"
py_binary   = "@gcr_io_distroless_python3"
go_binary   = "@gcr_io_distroless_static"
rust_binary = "@gcr_io_distroless_cc"
cc_binary   = "@gcr_io_distroless_cc"
```

Bases are pinned by digest in
`tools/publish/publish_segment.MODULE.bazel`. Bumping a digest is a
manual operation (`crane digest <image>:<tag>`).

`image_app_prefix` controls where each binary lands inside the image:
empty string places the binary at the tar root, otherwise at
`/<prefix>/<binary_name>`. Leading/trailing slashes and `..` segments
are rejected.

### Component Grouping

Modules can be grouped into three version scopes:

| Scope | Tag format | Description |
|-------|-----------|-------------|
| Repo-wide | `v{version}` | Default for unlisted modules |
| Component set | `{set_name}/v{version}` | Coordinated group (e.g., all Java modules) |
| Independent | `{component_id}/v{version}` | Own version lifecycle |

```toml
[component_sets.java_all]
modules = ["//modules/java_lib", "//modules/java_app"]

[components]
independent = ["//modules/cpp_library"]
```

### Release Placeholders

| Placeholder | Schema types | Example |
|-------------|-------------|---------|
| `{major}`, `{minor}`, `{patch}` | semver | `1.2.3` |
| `{YYYY}`, `{MM}`, `{DD}` | calver, gitdate | `2026.04.07` |
| `{git_count}` | gitdate | `42` |

### Dev Placeholders

| Placeholder | Description | Example |
|-------------|-------------|---------|
| `{next_version}` | Next release version | `1.2.4` |
| `{git_count}` | Commits since last tag | `7` |
| `{git_commit}` | Short commit hash | `abc1234` |

## Direct Invocation (Advanced)

Individual `:publish` and `:publish_image` targets can be invoked
directly with `PUBLISH_VERSION`:

```bash
# Artifact track
PUBLISH_VERSION=1.2.3 bazel run --config=publish //modules/java_lib:publish

# With PUBLISH_MODE for Maven SNAPSHOT
PUBLISH_VERSION=1.2.3 PUBLISH_MODE=dev bazel run --config=publish //modules/java_lib:publish

# Image track — pushes to <PUBLISH_DOCKER_URL>/<PUBLISH_DOCKER_REPO>/<artifact_id>:<PUBLISH_VERSION>
PUBLISH_VERSION=1.2.3 bazel run --config=publish //modules/java_app:publish_image

# Dry-run image push — prints the resolved coordinate without contacting the registry
PUBLISH_VERSION=1.2.3 bazel run --config=publish //modules/java_app:publish_image -- --dry-run
```

| Env var | Description |
|---------|-------------|
| `PUBLISH_VERSION` | Version string (required for both tracks) |
| `PUBLISH_MODE` | `dev` or `release` — affects Maven repo selection (snapshot vs release) and appends `-SNAPSHOT` to version |
| `PUBLISH_DOCKER_URL` | Override the build-flag-default OCI registry URL |
| `PUBLISH_DOCKER_REPO` | Override the build-flag-default OCI repository |
| `DRY_RUN` | Artifact track only — set to `1` to print URL without uploading |

`bazel build :publish_image` constructs all artifacts (base layer pull,
app tar, image, push launcher) without pushing. Push happens only at
`bazel run` time.

### Macro Reference

| Macro | Used for | Upload mode |
|-------|----------|-------------|
| `java_publish` | Java libraries (JAR) | Maven |
| `java_binary_publish` | Java apps (fat `_deploy.jar`) | Maven |
| `python_publish` | Python libraries (wheel) | PyPI |
| `binary_bundle_publish` | App binaries (zip) | Maven |
| `library_archive_publish` | Libraries (zip) | Maven |
| `image_publish` | App binaries (OCI container image) | Docker registry |

Language-specific macros are in `//tools/publish/lang/`:
- `java_publish_defs.bzl` — Java JAR publishing
- `python_publish_defs.bzl` — Python wheel publishing (requires `rules_python`)
- `generic_publish_defs.bzl` — Binary bundles and library archives
- `image_publish_defs.bzl` — OCI container images for any binary kind

The core `artifactory_upload` macro is in `//tools/publish:publish_defs.bzl`.

## Configuration

### Build Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--//tools/publish:url` | (empty) | Base URL of the artifact (Maven/PyPI) registry |
| `--//tools/publish:platform` | `artifactory` | Platform: `artifactory`, `nexus`, or `gitea` |
| `--//tools/publish:owner` | (empty) | Package owner/namespace (Gitea only) |
| `--//tools/publish:maven_release_repo` | (empty) | Maven release repository name |
| `--//tools/publish:maven_snapshot_repo` | (empty) | Maven snapshot repository name |
| `--//tools/publish:pypi_repo` | (empty) | PyPI repository name |
| `--//tools/publish:generic_repo` | (empty) | Generic repository name (fallback for all artifact modes) |
| `--//tools/publish:docker_url` | (empty) | OCI registry URL — pushes go to `<docker_url>/<docker_repo>/<artifact_id>:<version>` |
| `--//tools/publish:docker_repo` | (empty) | OCI repository name; falls back to `generic_repo` |

### Repository Resolution

Each `:publish` target resolves its repository name at runtime based on its
upload mode and `PUBLISH_MODE`:

| Mode | Resolution chain |
|------|-----------------|
| Maven (`java_publish`, `java_binary_publish`, `binary_bundle_publish`, `library_archive_publish`) | `PUBLISH_MODE=dev` → `maven_snapshot_repo`; otherwise → `maven_release_repo`; fallback → `generic_repo`; else fail |
| PyPI (`python_publish`) | `pypi_repo` → `generic_repo` → fail |
| Generic | `generic_repo` → fail |
| OCI (`image_publish`) | `docker_repo` → `generic_repo` → fail. URL resolves from `docker_url` (no fallback). Snapshot/release discrimination is encoded in `PUBLISH_VERSION` (the tag), not the repo. |

Each step checks the runtime env var first (e.g., `PUBLISH_MAVEN_RELEASE_REPO`),
then the `.bazelrc` flag default. If nothing is configured, the target fails with
a message showing exactly which flag to set.

If `repo_name` is passed explicitly in a macro, it is used directly — no
resolution chain, no fallback.

### Shared Team Config (`.bazelrc`)

```
build:publish --//tools/publish:url=https://registry.invalid/artifactory
build:publish --//tools/publish:platform=artifactory
build:publish --//tools/publish:maven_release_repo=libs-release-local
build:publish --//tools/publish:maven_snapshot_repo=libs-snapshot-local
build:publish --//tools/publish:pypi_repo=pypi-local
build:publish --//tools/publish:generic_repo=generic-local
build:publish --//tools/publish:docker_url=https://registry.invalid
build:publish --//tools/publish:docker_repo=docker-local
```

### Per-Developer Overrides (`user.bazelrc`)

```
# Override registry for local testing (gitignored)
build:publish --//tools/publish:url=https://my-local-gitea:3000
build:publish --//tools/publish:platform=gitea
build:publish --//tools/publish:owner=myuser
build:publish --//tools/publish:maven_release_repo=maven-releases
build:publish --//tools/publish:maven_snapshot_repo=maven-snapshots
```

## Authentication

All authentication flows share a single credential source: `~/.netrc`.

### Local Setup

Create `~/.netrc` with your registry credentials:

```
machine registry.invalid
  login admin
  password <api-token>
```

Restrict permissions: `chmod 600 ~/.netrc`

This file is used by:
- **Bazel downloads** via the credential helper (`tools/publish/credential-helper`)
- **Artifact uploads** via `curl --netrc` in `publish_artifact.sh` (all modes: Maven, PyPI, generic)
- **Image pushes** via `tools/publish/docker_login_helper.py`, which reads the `.netrc` entry for the registry host and merges `auths.<host>` into `~/.docker/config.json` before each push. `oci_push` (via `go-containerregistry`) then performs the Docker Registry v2 token exchange itself.

### Credential Helper (Bazel downloads)

The credential helper at `tools/publish/credential-helper` implements the
[Bazel credential helper protocol](https://github.com/bazelbuild/proposals/blob/main/designs/2022-06-07-bazel-credential-helpers.md).
It reads `~/.netrc` and returns Basic auth headers for matching hosts.

Enable it in `.bazelrc` (or `user.bazelrc`):

```
common --credential_helper=%workspace%/tools/publish/credential-helper
```

### CI Setup

In CI (e.g., GitHub Actions), create `~/.netrc` from secrets:

```yaml
- name: Configure registry credentials
  run: |
    cat > ~/.netrc << EOF
    machine registry.invalid
      login ${{ secrets.REGISTRY_USER }}
      password ${{ secrets.REGISTRY_TOKEN }}
    EOF
    chmod 600 ~/.netrc
```

## Maven Coordinate Scheme

Non-Java artifacts use Maven coordinates as a common denominator for uniform
artifact discovery in Artifactory:

- **Group:** `com.monorepo.test` (from `DEFAULT_MAVEN_GROUP` in `publish_defs.bzl`)
- **Artifact:** kebab-case module name (e.g., `cpp-app`)
- **Version:** resolved by mint or set via `PUBLISH_VERSION`
- **Classifier:** platform string for native binaries (e.g., `linux-x86_64`)
- **Example:** `com/monorepo/test/cpp-app/1.2.3/cpp-app-1.2.3-linux-x86_64.zip`

## OCI Coordinate Scheme

Container images use the standard OCI coordinate shape:

```
<PUBLISH_DOCKER_URL>/<docker_repo>/<artifact_id>:<PUBLISH_VERSION>
```

- **URL:** `docker_url` flag or `PUBLISH_DOCKER_URL` env var (scheme stripped)
- **Repo:** `docker_repo` flag or `PUBLISH_DOCKER_REPO` env var; falls back to `generic_repo`
- **Artifact:** kebab-case module name (e.g., `java-app`)
- **Tag:** `PUBLISH_VERSION` — snapshot vs. release is encoded in the version string itself, not in the repo name
- **Example:** `registry.invalid/docker-local/java-app:1.2.3`

`group_id` is dropped — OCI registries lack the hierarchical group concept.
Server-side namespacing is configured at the registry admin level.

Images are single-platform `linux/amd64` for the MVP; multi-arch is a
future enhancement (tracked in `IMAGE_PUBLISH_SPEC.md`).

## Platform Support

| Platform | Maven | PyPI | Generic |
|----------|-------|------|---------|
| Artifactory | `{URL}/{repo}/{group-path}/{artifact}/{ver}/{file}` | `{URL}/{repo}/` | `{URL}/{repo}/{path}/{file}` |
| Nexus | `{URL}/repository/{repo}/{group-path}/{artifact}/{ver}/{file}` | `{URL}/repository/{repo}/` | `{URL}/repository/{repo}/{path}/{file}` |
| Gitea | `{URL}/api/packages/{owner}/maven/...` | `{URL}/api/packages/{owner}/pypi` | `{URL}/api/packages/{owner}/generic/...` |

All artifact uploads use `curl` with `--netrc` authentication. PyPI wheels are uploaded via the
standard PyPI upload protocol (multipart POST), with the wheel automatically repackaged
at publish time to embed the correct `PUBLISH_VERSION` in metadata and filename.

OCI image push is vendor-agnostic — `oci_push` (via `go-containerregistry`)
speaks the standard Docker Registry v2 protocol against any compliant
registry (Artifactory, Harbor, Nexus, ECR, GCR, ghcr.io, …). No
per-vendor URL templating is needed; see [OCI Coordinate Scheme](#oci-coordinate-scheme).

## Adding Publish Targets to New Modules

### Binary (C++, Rust, Go, Python app)

```python
load("//tools/publish/lang:generic_publish_defs.bzl", "binary_bundle_publish")

binary_bundle_publish(
    name = "publish",
    binary_target = ":my_app",
    artifact_id = "my-app",
)
```

### Java App (fat JAR)

```python
load("//tools/publish/lang:java_publish_defs.bzl", "java_binary_publish")

java_binary_publish(
    name = "publish",
    binary_target = ":my_java_app",
    artifact_id = "my-java-app",
)
```

Publishes the `_deploy.jar` implicit output of a `java_binary` — a single
self-contained JAR with all classpath dependencies merged in and `Main-Class`
set in the manifest. Consumers run it with `java -jar my-java-app.jar` or
depend on it as a Maven artifact. To fall back to the polyglot zip-bundle
behaviour (e.g., when the binary's runfiles include sibling files callers
need), tag the `java_binary` with `tags = ["publish_bundle"]`.

### Library (C++, Rust, Go)

```python
load("//tools/publish/lang:generic_publish_defs.bzl", "library_archive_publish")

library_archive_publish(
    name = "publish",
    library_target = ":my_lib",
    artifact_id = "my-lib",
    hdrs = glob(["include/**/*.h"]),  # C++ headers
)
```

### Java Library

```python
load("//tools/publish/lang:java_publish_defs.bzl", "java_publish")

java_publish(
    name = "publish",
    library_target = ":my_java_lib",
    artifact_id = "my-java-lib",
)
```

### Python Library

```python
load("//tools/publish/lang:python_publish_defs.bzl", "python_publish")

python_publish(
    name = "publish",
    library_target = ":my_python_lib",
    distribution = "my-python-lib",
)
```

### OCI Image (any binary kind)

For most cases, gazelle emits `:publish_image` automatically alongside
`:publish` when the canonical kind has a configured `[image_bases]`
entry — you don't write it by hand. Direct usage is for cases that
need extra layers or custom entrypoint expansion:

```python
load("//tools/publish/lang:image_publish_defs.bzl", "image_publish")

image_publish(
    name          = "publish_image",
    binary_target = ":my_app",
    base          = "@gcr_io_distroless_static",
    artifact_id   = "my-app",
    entrypoint    = ["/app/my_app"],
    strip_prefix  = package_name(),  # for go/rust: package_name() + "/my_app_"
    extra_layers  = [":config_layer"],  # optional
)
```

For Java images, point `binary_target` at the canonical's `_deploy.jar`
(e.g., `":java_app_deploy.jar"`) and use the JVM entrypoint pattern:

```python
image_publish(
    name          = "publish_image",
    binary_target = ":java_app_deploy.jar",
    base          = "@gcr_io_distroless_java17",
    artifact_id   = "java-app",
    entrypoint    = ["java", "{runtime_args}", "-jar", "/app/java_app_deploy.jar"],
    runtime_args  = ["-Xmx2g", "-XX:+UseG1GC"],  # spliced into {runtime_args}
    strip_prefix  = package_name(),
)
```

`{runtime_args}` is a single-occurrence placeholder expanded at macro
evaluation. Empty `runtime_args` collapses the slot. `cmd` (Docker CMD,
overridable at `docker run` time) passes through unmodified.

## Auto-Generating `:publish` and `:publish_image` Targets (Gazelle)

A [Gazelle language extension](./gazelle) auto-generates `:publish` and
`:publish_image` targets from a single BUILD-file convention: **the rule
whose name equals the package basename is the canonical publishable
target.** This replaces hand-written publish blocks for any module that
follows the convention. Binary canonicals receive both rules; library
canonicals receive `:publish` only.

```bash
# Regenerate :publish targets across the repo
bazel run //:publish_gen

# Preview without writing
bazel run //:publish_gen -- -mode diff

# Fail on convention violations (used in CI)
bazel run //:publish_gen -- -publish_strict
```

### Convention → Macro Mapping

Given `modules/python_lib/BUILD` containing `py_library(name = "python_lib", ...)`,
the extension emits a `python_publish` target paired with that library. Mapping from
canonical source-rule kind to publish-macro kind:

| Canonical kind | Publish macro | Role |
|----------------|---------------|------|
| `cc_binary`, `go_binary`, `py_binary`, `rust_binary` | `binary_bundle_publish` | binary |
| `java_binary` | `java_binary_publish` (fat JAR) | binary |
| `cc_library`, `go_library`, `rust_library` | `library_archive_publish` | library |
| `java_library` | `java_publish` | library |
| `py_library` | `python_publish` | library |

`py_library` targets set `distribution` (prefix from `.publish.toml`'s
`[conventions].python_distribution_prefix` + kebab-cased basename); the rest
set `artifact_id` (kebab-cased basename). For `cc_library`, the canonical
rule's `hdrs` expression is copied so the published archive's header fan-out
matches what the library exposes.

A `java_binary` carrying `tags = ["publish_bundle"]` falls back to
`binary_bundle_publish`, matching the polyglot zip-bundle behaviour the
other binary kinds use. This is for Java apps whose runfiles include
sibling files callers expect to receive alongside the JAR.

### Image Emission

For each binary canonical (`cc_binary`, `go_binary`, `java_binary`,
`py_binary`, `rust_binary`), gazelle additionally emits an
`image_publish` rule named `"publish_image"` if `[image_bases]` in
`.publish.toml` provides a base for that kind:

| Attribute | Source |
|-----------|--------|
| `name` | `"publish_image"` |
| `binary_target` | `:<canonical>` (or `:<canonical>_deploy.jar` for `java_binary`) |
| `artifact_id` | kebab-cased package basename |
| `base` | `[image_bases][<kind>]` |
| `entrypoint` | per-kind formula |
| `app_prefix` | `[conventions].image_app_prefix` (default `"app"`) |
| `strip_prefix` | per-kind formula |

Per-kind entrypoint and `strip_prefix` formulas (where `<P>` is
`/<app_prefix>/<binary_name>`):

| Kind | `binary_target` | `strip_prefix` | `entrypoint` |
|------|-----------------|----------------|--------------|
| `java_binary` | `:<name>_deploy.jar` | `<package>` | `["java", "{runtime_args}", "-jar", "<P>_deploy.jar"]` |
| `go_binary` | `:<name>` | `<package>/<name>_` | `["<P>"]` |
| `rust_binary` | `:<name>` | `<package>/<name>_` | `["<P>"]` |
| `cc_binary` | `:<name>` | `<package>` | `["<P>"]` |
| `py_binary` | `:<name>` | `<package>` | `["<P>"]` |

`runtime_args`, `cmd`, and `extra_layers` are never auto-populated —
hand-edit them after the first emission and gazelle will preserve the
values on re-runs. `base` is also never overwritten on re-runs (a base
change in `.publish.toml` requires hand-editing each existing rule or
removing them and re-running `publish_gen`).

A binary kind missing from `[image_bases]` produces a warning at
`publish_gen` time and no `:publish_image` is emitted; `:publish` is
unaffected. Under `-publish_strict`, the warning becomes a fatal error.

### Scope and Opt-Out

- **Path allowlist** — only packages matching `[conventions].path_patterns` in
  `.publish.toml` are considered. Default is `["modules/**"]`. Patterns support
  `exact`, `foo/*` (immediate children), and `foo/**` (recursive).
- **Per-package opt-out** — three directives, one per scope:
  - `# gazelle:publish_ignore` — suppress both `:publish` and `:publish_image`.
  - `# gazelle:publish_ignore_artifact` — suppress `:publish` only.
  - `# gazelle:publish_ignore_image` — suppress `:publish_image` only.
- **Rename to opt out** — a rule whose name differs from the package basename is
  invisible to the extension (no warning, no target emitted).
- **Per-rule kind override** — `java_binary` with `tags = ["publish_bundle"]`
  emits `binary_bundle_publish` instead of `java_binary_publish`. The image
  track ignores this tag — both Java image variants still want a Java image,
  so the formula keys on the canonical's actual kind.

### Enforcement

In default mode, convention violations are logged as warnings:
- A package in scope with no rule whose name matches the basename.
- A canonical rule whose kind is not publishable.
- A binary canonical whose kind has no `[image_bases]` entry (image emission skipped).

`-publish_strict` escalates the first violation to a fatal error. CI runs
`bazel run //:publish_gen -- -publish_strict` followed by `git diff --exit-code`,
which together catch both convention drift and forgotten regenerations.
