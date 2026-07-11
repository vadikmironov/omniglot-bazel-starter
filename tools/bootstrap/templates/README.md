# omniglot-bazel-starter

<!-- --- BEGIN user-managed --- -->
_Describe your project here. This section is yours — it is preserved when you
re-run the bootstrap tool, while the rest of this file is refreshed._
<!-- --- END user-managed --- -->

## Project Layout

- `{{code_dir}}/` — your code: modules, services, and apps
- `MODULE.bazel` — module definition, segmented by language for easy pruning
- `tools/` — toolchains, formatters, and per-language dependency configuration

Add a module under `{{code_dir}}/`, then `bazel build //...` and
`bazel test //...` to confirm it wires up. The toolchains are already
configured — no per-language setup required.

## Install Bazelisk

Toolchains are hermetic, so Bazelisk is the only thing you need installed — it
reads `.bazelversion` and fetches the matching Bazel release on demand.

```bash
# Auto: system install (apt/.deb) when root or passwordless sudo is available,
# otherwise a no-sudo install into ~/.local/bin (PATH wired into your shell rc)
tools/setup/install_bazelisk.sh

# Force one mode or the other
tools/setup/install_bazelisk.sh --user      # no sudo, ~/.local/bin
tools/setup/install_bazelisk.sh --system    # apt/.deb, prompts for sudo
```

Linux only. Run `bazel version` to verify (restart your shell first if the
installer added `~/.local/bin` to your PATH).

## Common Commands

```bash
# List runnable targets — apps, buildifier, venv (plain `//...` lists everything)
bazel query 'kind("(py|cc|go|java|rust)_binary|buildifier|_venv", //...)'

# Build / test everything
bazel build //...
bazel test //...                     # excludes lint tests — run lint separately

# Format source (all languages), then Bazel/Starlark files
bazel run //:buildifier.fix          # Windows: tools\buildifier.bat fix
bazel run //:format
```
# --- BEGIN feature:lint ---

Linting is a separate, generated step — per-target `lint_test` rules are emitted
by Gazelle and then run as tests:

```bash
bazel run //:lint_gen                # preview without writing: -- -mode diff
bazel test --test_tag_filters=lint //...
```
# --- END feature:lint ---

# --- BEGIN lang:python,java,rust,go ---
### Regenerate dependency locks

After editing a language's dependency manifest, refresh its lockfile:

```bash
# --- END lang:python,java,rust,go ---
# --- BEGIN lang:python ---
bazel run //tools/python:generate_requirements_lock.update            # Python — tools/python/requirements.in
# --- END lang:python ---
# --- BEGIN lang:java ---
REPIN=1 bazel run @omniglot-bazel-starter_maven_dependencies//:pin    # Java   — Maven artifacts
# --- END lang:java ---
# --- BEGIN lang:rust ---
CARGO_BAZEL_REPIN=1 bazel fetch @crates//...                          # Rust   — tools/rust/Cargo.toml
# --- END lang:rust ---
# --- BEGIN lang:go ---
bazel run @rules_go//go -- mod tidy                                   # Go     — go.mod / go.sum
# --- END lang:go ---
# --- BEGIN lang:python,java,rust,go ---
```
# --- END lang:python,java,rust,go ---

# --- BEGIN feature:custom_toolchains lang:cpp,python,java,go ---
## Custom Toolchains

Besides the hermetic defaults, optional host/local toolchains are selectable via
`--config` (machine-specific — install the toolchain first; setup lives under
`tools/<lang>/toolchains/`):

```bash
# --- END feature:custom_toolchains lang:cpp,python,java,go ---
# --- BEGIN feature:custom_toolchains lang:cpp ---
bazel build --config=gcc_host //...                      # C++ via host GCC
bazel build --config=clang_host //...                    # C++ via host Clang
# --- END feature:custom_toolchains lang:cpp ---
# --- BEGIN feature:custom_toolchains lang:python ---
bazel build --config=python3_13_host //...               # Python via host interpreter
# --- END feature:custom_toolchains lang:python ---
# --- BEGIN feature:custom_toolchains lang:java ---
bazel build --config=java_17_local_corretto_jdk //...    # Java via local Corretto JDK 17
bazel build --config=java_17_remote_corretto_jdk //...   # Java via downloaded Corretto JDK 17
# --- END feature:custom_toolchains lang:java ---
# --- BEGIN feature:custom_toolchains lang:go ---
bazel build --config=go_local_sdk //...                  # Go via local SDK (USE_LOCAL_GO_SDK=1)
# --- END feature:custom_toolchains lang:go ---
# --- BEGIN feature:custom_toolchains lang:cpp,python,java,go ---
```
# --- END feature:custom_toolchains lang:cpp,python,java,go ---

# --- BEGIN feature:remote_cache ---
## Remote Cache (BuildBuddy)

Local builds can share a BuildBuddy remote cache for faster builds:

```bash
# 1. Copy the template and add your API key
cp user.bazelrc.template user.bazelrc
# Edit user.bazelrc — uncomment and set your BuildBuddy API key

# 2. Build with the remote cache enabled
bazel build --config=remote-cache //...
```

`user.bazelrc` is gitignored. See `user.bazelrc.template` for the full list of
flags it documents.
# --- END feature:remote_cache ---
# --- BEGIN feature:coverage ---

## Code Coverage

Coverage works across all languages through `bazel coverage`, merged into one LCOV
report and rendered to HTML by the hermetic lcov `genhtml` (no system `lcov` needed):

```bash
# Collect coverage across the repo (merged LCOV)
bazel coverage --combined_report=lcov //...

# Render the HTML report to ./coverage-html/, then open index.html
bazel run //tools/coverage:report
```
# --- END feature:coverage ---
# --- BEGIN feature:coverage lang:cpp ---

C++ uses LLVM source-based coverage on the default Clang toolchain; add
`--config=gcc_hermetic` to measure the GCC build (gcov) instead.
# --- END feature:coverage lang:cpp ---
# --- BEGIN feature:coverage ---

The `coverage-html/` output is ready to publish to GitHub Pages or a self-hosted
TeamCity instance — wire it into your CI.
# --- END feature:coverage ---
# --- BEGIN feature:profiling ---

## Profiling

CPU and memory profiling driven by tagged benchmark targets, rendered to
flamegraphs by a fully hermetic toolchain (in-process capture → pprof → folded
stacks → inferno SVG — no system tools needed):

```bash
# List profilable targets (tags: profiling-cpu / profiling-mem)
bazel run //tools/profile -- --list

# Profile a target: SVG flamegraph + top-N table into ./profile-out/
bazel run //tools/profile -- //path/to:bench_target

# Real benchmark timings — no profiler attached (CPU benches only)
bazel run //tools/profile -- //path/to:bench_target --measure

# Terminal flamegraph viewer; --all profiles every discovered target
bazel run //tools/profile -- //path/to:bench_target --view
```

To make a target profilable:

- **CPU**: a criterion-bench `rust_binary` configured with pprof-rs's
  `PProfProfiler(Output::Protobuf)`, tagged `profiling-cpu`.
- **Memory**: a one-shot `rust_binary` that links `tikv-jemallocator`
  (`profiling` feature) as the global allocator and dumps a `jemalloc_pprof`
  profile to `$MEMPROF_OUT`, tagged `profiling-mem`. Memory profiling is
  Linux-only (`jemalloc_pprof` supports only Linux) — constrain such targets
  with `target_compatible_with = ["@platforms//os:linux"]`.

Never quote timings from profile runs — use `--measure`; profiling distorts
timing. Memory observations describe jemalloc (the heap profiler lives in the
allocator), and heap profiles record live allocations at dump time.
# --- END feature:profiling ---
# --- BEGIN lang:python ---

## Pre-commit Hooks

Fast local formatting/linting checks (< 2s, no Bazel startup). The `pre-commit`
binary comes from the project virtual environment:

```bash
# Create/update .venv with all dev tools including pre-commit (one-time)
bazel run //tools/python:generate_virtual_env

# Install the git hook (one-time), then it runs on every commit
.venv/bin/pre-commit install

# Run on all files on demand
.venv/bin/pre-commit run --all-files
```

Hooks are configured in `.pre-commit-config.yaml`.
# --- END lang:python ---
# --- BEGIN feature:publish ---

## Publishing

Artifact publishing is orchestrated by `mint`, which resolves versions from git
tags and `.publish.toml` and pushes to Maven / PyPI registries and OCI images.

```bash
# Publish all modules (dev version) — both tracks
bazel run //tools/publish:mint -- --mode dev --include-pub-targets all

# Publish a release from a branch
bazel run //tools/publish:mint -- --mode release --branch main --include-pub-targets all

# Print the version plan without building
bazel run //tools/publish:mint -- --mode dev --include-pub-targets all --dry-run
```

`:publish` targets for modules that follow the canonical BUILD convention are
auto-generated — run `bazel run //:publish_gen` after adding modules. See
`tools/publish/README.md` for registry/credential setup.
# --- END feature:publish ---
