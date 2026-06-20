# `image_publish` — Spec

**Status:** implementation complete. All 12 binary modules in `modules/` emit `:publish_image` via gazelle; mint orchestrates artifact + image tracks under `--include-pub-targets {artifacts,images,all}`.

A new publish macro `image_publish` extends the publish infrastructure to produce OCI container images alongside the existing artifact uploads (Maven/PyPI). Each binary module emits both a `:publish` target (Maven/PyPI artifact) and a `:publish_image` target (OCI image) by default.

## Macro

### Surface

```python
image_publish(
    name              = "...",
    binary_target     = "...",
    base              = "...",
    artifact_id       = "...",
    entrypoint        = [...],
    runtime_args      = [...],
    cmd               = [...],
    app_prefix        = "app",
    strip_prefix      = "",
    extra_layers      = [...],
    visibility        = None,
)
```

### Generated targets

Five Bazel targets per call. Intermediates use underscore-prefix naming and `visibility = ["//visibility:private"]`.

| Target | Kind | Visibility |
|---|---|---|
| `_<name>_app_layer` | `tar` (from `@tar.bzl`) | private |
| `_<name>_image` | `oci_image` | private |
| `_<name>_push` | `oci_push` | private |
| `_<name>_gen` | `write_file` | private |
| `<name>` | `sh_binary` | inherits package |

### Per-kind entrypoint and strip_prefix formula

| Kind | `binary_target` reroute | `strip_prefix` (gazelle-emitted) | entrypoint formula |
|---|---|---|---|
| `java_binary` | append `_deploy.jar` | `package_name()` | `["java", "{runtime_args}", "-jar", "<prefix-path>_deploy.jar"]` |
| `go_binary` | (none) | `package_name() + "/" + name + "_"` | `["<prefix-path>"]` |
| `rust_binary` | (none) | `package_name() + "/" + name + "_"` | `["<prefix-path>"]` |
| `cc_binary` | (none) | `package_name()` | `["<prefix-path>"]` |
| `py_binary` | (none) | `package_name()` | `["<prefix-path>"]` |

`strip_prefix` removes `tar.bzl`'s preserved workspace-relative path so the
binary lands at `/<app_prefix>/<name>` rather than
`/<app_prefix>/<package>/<name>`. `go_binary`/`rust_binary` need the trailing
`/<name>_` because rules_go/rules_rust add an internal `<name>_/` subdirectory
to the binary's output path.

`{runtime_args}` is substituted with the `runtime_args` list at macro expansion. Empty `runtime_args` collapses the slot. Multiple placeholders fail loudly. Supplying `runtime_args` for a kind whose formula has no placeholder fails loudly. `cmd` passes through unmodified to `oci_image.cmd`.

### Layer composition

```python
tar(
    name = "_<name>_app_layer",
    srcs = [binary_target],
    mutate = mutate(
        package_dir = "<app_prefix>",     # no leading slash; tar.bzl handles
        strip_prefix = "<strip_prefix>",  # per-kind, gazelle-emitted
    ),
)

oci_image(
    name = "_<name>_image",
    base = base,
    tars = [":_<name>_app_layer"] + extra_layers,
    entrypoint = expanded_entrypoint,
    cmd = cmd,
)
```

`tar.bzl` includes runfiles automatically when `srcs` is an executable target — no `include_runfiles` flag. Single app layer per call; users add more via `extra_layers`.

**Why `tar.bzl` over `pkg_tar`:** rules_oci [PR #808](https://github.com/bazel-contrib/rules_oci/pull/808) ("chore(docs): stop recommending pkg_tar — It has a lot of problems and we can't fix them") deprecates `pkg_tar` for OCI use. The killer issue is layer-hash determinism: `pkg_tar`'s file ordering / mtime / uid-gid quirks produce different tar bytes on different builds, busting OCI registry layer-cache deduplication. `tar.bzl` ships its own `bsdtar` and is reproducible by design.

## Gazelle auto-emission

For each canonical binary rule (`cc_binary`, `go_binary`, `java_binary`, `py_binary`, `rust_binary`) discovered in scope, gazelle emits an `image_publish` rule named `"publish_image"` alongside the existing `:publish`.

### Auto-populated attributes

| Attribute | Source | Mergeable |
|---|---|---|
| `name` | `"publish_image"` | n/a |
| `binary_target` | `:<canonical>` (or `:<canonical>_deploy.jar` for `java_binary`) | yes |
| `artifact_id` | kebab-cased package basename | yes |
| `base` | `.publish.toml [image_bases][<kind>]` | no |
| `entrypoint` | per-kind formula | yes |
| `app_prefix` | `.publish.toml [conventions].image_app_prefix` (default `"app"`) | yes |
| `strip_prefix` | per-kind formula (see table above) | yes |
| `runtime_args` | never auto-populated | no |
| `cmd` | never auto-populated | no |
| `extra_layers` | never auto-populated | n/a |

### Per-package opt-out directives

| Directive | Effect |
|---|---|
| `# gazelle:publish_ignore` | suppress both `:publish` and `:publish_image` |
| `# gazelle:publish_ignore_artifact` | suppress `:publish` only |
| `# gazelle:publish_ignore_image` | suppress `:publish_image` only |

### Configuration validation

`[conventions].image_app_prefix`:
- Empty string OK.
- Leading or trailing `/` rejected (fatal).
- `..` segments rejected (fatal).

`[image_bases]`:
- Maps binary kind → base image label.
- Missing entry for a kind in scope: warning by default, fatal under `-publish_strict`. `:publish_image` is not emitted for that package; the `:publish` target is unaffected.

## Module setup

### MODULE.bazel — added to `tools/publish/publish_segment.MODULE.bazel`

```python
bazel_dep(name = "rules_oci", version = "2.3.0")
bazel_dep(name = "tar.bzl",   version = "0.10.1")

oci = use_extension("@rules_oci//oci:extensions.bzl", "oci")

oci.pull(
    name      = "gcr_io_distroless_java17",
    image     = "gcr.io/distroless/java17-debian13",
    digest    = "sha256:<pinned>",
    platforms = ["linux/amd64"],
)
oci.pull(
    name      = "gcr_io_distroless_python3",
    image     = "gcr.io/distroless/python3-debian13",
    digest    = "sha256:<pinned>",
    platforms = ["linux/amd64"],
)
oci.pull(
    name      = "gcr_io_distroless_static",
    image     = "gcr.io/distroless/static-debian13",
    digest    = "sha256:<pinned>",
    platforms = ["linux/amd64"],
)
oci.pull(
    name      = "gcr_io_distroless_cc",
    image     = "gcr.io/distroless/cc-debian13",
    digest    = "sha256:<pinned>",
    platforms = ["linux/amd64"],
)

use_repo(
    oci,
    "gcr_io_distroless_java17",
    "gcr_io_distroless_python3",
    "gcr_io_distroless_static",
    "gcr_io_distroless_cc",
)
```

### `.publish.toml` defaults

```toml
[conventions]
image_app_prefix = "app"

[image_bases]
java_binary = "@gcr_io_distroless_java17"
py_binary   = "@gcr_io_distroless_python3"
go_binary   = "@gcr_io_distroless_static"
rust_binary = "@gcr_io_distroless_cc"
cc_binary   = "@gcr_io_distroless_cc"
```

### Naming convention

- Registry-source prefix `gcr_io_` for namespace clarity across future multi-source pulls.
- Language version included where applicable (`java17`, `python3`); OS version excluded.
- `static`/`cc` carry no version suffix — they encode flavor, not version.

### Pinning

All bases pinned by digest. Single platform (`linux/amd64`) for the MVP. Bumping is manual via `crane digest <image>:<tag>`.

## Publish target topology

### Per-module shape

| Target | Macro / Mode | When emitted |
|---|---|---|
| `:publish` | `java_publish`, `python_publish`, `java_binary_publish`, `binary_bundle_publish`, `library_archive_publish` (Maven/PyPI) | always, unless suppressed by `publish_ignore` / `publish_ignore_artifact` |
| `:publish_image` | `image_publish` (OCI) | binaries only, unless suppressed by `publish_ignore` / `publish_ignore_image`, AND `[image_bases]` has an entry for the kind |

### Build flags

| Flag | Used by | Notes |
|---|---|---|
| `--//tools/publish:url` | Maven/PyPI | existing — REST API endpoint |
| `--//tools/publish:docker_url` | OCI | new — registry endpoint |
| `--//tools/publish:maven_release_repo` | Maven (`PUBLISH_MODE=release`) | existing |
| `--//tools/publish:maven_snapshot_repo` | Maven (`PUBLISH_MODE=dev`) | existing |
| `--//tools/publish:pypi_repo` | PyPI | existing |
| `--//tools/publish:docker_repo` | OCI | new — single repo; tag-driven snapshot/release discrimination via `PUBLISH_VERSION` |
| `--//tools/publish:generic_repo` | fallback for any of the above | existing |

### OCI coordinate scheme

```
<PUBLISH_DOCKER_URL>/<docker_repo>/<artifact_id>:<PUBLISH_VERSION>
```

`group_id` is dropped for image coordinates — OCI registries lack the hierarchical group concept. Server-side namespacing is configured at the Artifactory admin level, not encoded in the coordinate.

### mint orchestration

- mint discovers both `:publish` and `:publish_image` per in-scope module via Bazel query and runs whichever exists.
- Targets run sequentially in stable order (artifact then image, per module).
- First failure aborts the run; no rollback.
- Required CLI flag: `--include-pub-targets {artifacts,images,all}`. Mandatory choice (no default) — both registries have non-trivial blast radius and different audit trails, so the run states intent on every invocation. `argparse` rejects unknown values; engine entry points re-validate to catch direct API misuse.
- `--dry-run` lists every target the chosen `--include-pub-targets` would invoke. Tracks deselected by the chosen value are still listed but annotated `(skipped: --include-pub-targets=<value>)`.
- Component sets and version schemas in `.publish.toml` work unchanged.

## Auth flow

### Phase 1 (MVP)

A new `docker-login-helper` binary is invoked by the `:publish_image` wrapper before `oci_push`. It reads `.netrc` for the registry hostname and merges `auths.<host>` into `~/.docker/config.json`. `go-containerregistry` (used by `oci_push`) reads `config.json` and performs the Docker Registry v2 token exchange itself per push.

### Two helpers

| Helper | Constraint | Tooling |
|---|---|---|
| `tools/publish/credential-helper` (existing) | plain shell (Bazel-fetch bootstrap) | bash + coreutils |
| `tools/publish/docker-login-helper` (new) | Bazel-built (invoked at `bazel run` time) | bash + `rules_jq` + `flock` |

Shared `.netrc` parsing factors into a sourced library function reused by both.

### `config.json` merge semantics

`docker-login-helper` owns exactly one key: `auths.<host>`.

| Pre-existing state | Action |
|---|---|
| File absent | create with our entry, mode `0600` |
| File exists, no `auths` block | add `auths` block, preserve other top-level fields |
| File exists, no entry for our host | append entry, preserve everything else |
| File has stale `auth` for our host | overwrite the `auth` slot in place |
| File has `registrytoken` / `identitytoken` for our host | replace entire entry with fresh basic auth |
| File has `credHelpers.<our-host>` | **fail loudly** (auth-delegation conflict) |
| File has top-level `credsStore` | **warn loudly**, proceed |
| File is malformed JSON | **fail loudly**, refuse to overwrite |
| File has unrecognized top-level fields (`plugins`, `currentContext`, etc.) | preserve verbatim |

Atomicity: temp file + atomic rename. Mode forced to `0600` after every write. Concurrency: `flock` on `~/.docker/config.json.lock` serializes parallel invocations.

### `PUBLISH_PLATFORM`

Unchanged — remains server-type-only (`artifactory` / `nexus` / `gitea`), governing the artifact (Maven/PyPI) flow. Image auth is invoked via `docker-login-helper` directly; no new platform value introduced.

### Dry run

`bazel run :publish_image -- --dry-run` is forwarded to `oci_push`'s built-in `--dry-run`. Prints the resolved coordinate without pushing.

## Wrapper script

The `:publish_image` wrapper runs three phases at `bazel run` time. `set -euo pipefail` at top of wrapper.

```bash
# 1. Resolve config (env-var-or-default chain)
PUBLISH_DOCKER_URL="${PUBLISH_DOCKER_URL:-${PUBLISH_DOCKER_URL_DEFAULT:-}}"
[[ -n "${PUBLISH_DOCKER_URL}" ]] || { echo 'ERROR: ...' >&2; exit 1; }

PUBLISH_DOCKER_REPO="${PUBLISH_DOCKER_REPO:-${PUBLISH_DOCKER_REPO_DEFAULT:-}}"
[[ -n "${PUBLISH_DOCKER_REPO}" ]] || \
    PUBLISH_DOCKER_REPO="${PUBLISH_GENERIC_REPO:-${PUBLISH_GENERIC_REPO_DEFAULT:-}}"
[[ -n "${PUBLISH_DOCKER_REPO}" ]] || { echo 'ERROR: ...' >&2; exit 1; }

[[ -n "${PUBLISH_VERSION:-}" ]] || { echo 'ERROR: ...' >&2; exit 1; }

# 2. Authenticate
REGISTRY_HOST="${PUBLISH_DOCKER_URL#http://}"
REGISTRY_HOST="${REGISTRY_HOST#https://}"
REGISTRY_HOST="${REGISTRY_HOST%%/*}"
"${RUNFILES}/_main/tools/publish/docker-login-helper" --registry="${REGISTRY_HOST}"

# 3. Push (with user-flag forwarding)
REPOSITORY="${PUBLISH_DOCKER_URL%/}/${PUBLISH_DOCKER_REPO}/<artifact_id>"
echo "Pushing ${REPOSITORY}:${PUBLISH_VERSION}" >&2
exec "${RUNFILES}/_main/<package>/_<name>_push" \
    --repository="${REPOSITORY}" \
    --tag="${PUBLISH_VERSION}" \
    "$@"
```

`<artifact_id>`, `<package>`, and `<name>` are macro-time substitutions written into the per-target wrapper. `--repository` and `--tag` are owned by the wrapper; user overrides via `"$@"` are forwarded but silently shadow our values.

`bazel build :publish_image` constructs all artifacts but does not push. `bazel run :publish_image` pushes; `-- --dry-run` is forwarded to `oci_push`.

## Follow-up items

- **Multi-platform support.** Natural axis is multi-arch Linux (amd64 + arm64) via `oci_image_index`. Windows / macOS are different problems treated as separate publishing tracks.
- **Renovate digest-bump for base images.** `customManagers` rule for `*.MODULE.bazel`.
- **JWT pre-fetch mode (Phase 2 auth).** For environments that audit static-cred-on-disk policy.
- **Migrate existing publish macros' intermediates to underscore-prefix.** Convention consistency once `image_publish` ships. Tracked in `.claude/memory/project_publish_underscore_prefix_migration.md`.
