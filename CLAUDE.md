# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build Commands

### Language-Specific Toolchain Selection
```bash
# C++ default is the hermetic LLVM/Clang toolchain (no flag needed).

# C++ with hermetic GCC (f0rmiga/gcc-toolchain, pinned GCC 15.2.0)
bazel build --config=gcc_hermetic //modules/cpp_app

# C++ hermetic GCC toolchain resolution debugging
bazel build --config=gcc_hermetic_debug //modules/cpp_app

# C++ with GCC host compiler (non-hermetic, system gcc, auto-discovered)
bazel build --config=gcc_host //modules/cpp_app

# C++ with Clang host compiler (non-hermetic, system clang, auto-discovered)
bazel build --config=clang_host //modules/cpp_app

# C++ with remote pinned compilers (downloaded on first use, link against host
# glibc): xPack GCC 15.2.0 / hermetic-llvm minimal clang 22.1.8 (~41 MB)
bazel build --config=gcc_remote //modules/cpp_app
bazel build --config=clang_remote //modules/cpp_app

# Python with local host interpreter (newest python3.X on PATH)
bazel build --config=python_host //modules/python_app

# Java with local host JDK (newest installed JDK)
bazel build --config=java_host //modules/java_app

# Go with local host SDK (newest discovered SDK)
bazel build --config=go_host //modules/go_app

# Python toolchain debugging
bazel build --config=python_host_debug //modules/python_app
```

## Linting and Formatting

### Automated Formatting
```bash
# Run formatting across entire codebase
//tools/format:format
```

### Automated Linting

```bash
# Generate or refresh per-target lint_test rules
bazel run //:lint_gen

# Run all lint tests
bazel test --test_tag_filters=lint //...

# Preview lint_gen changes without applying
bazel run //:lint_gen -- -mode diff
```

Per-package opt-out: `# gazelle:lint_ignore` at the top of a BUILD.
Per-target opt-out: `tags = ["no-lint"]` on the source rule.
Auto-fix workflow and full reference: [tools/lint/README.md](tools/lint/README.md).

### Language-Specific Linting
- **Python**: ruff (linting), ty (type checking), ruff (formatting)
- **Rust**: clippy (linting), rustfmt (formatting)
- **C++**: clang-tidy (linting), clang-format (formatting)
- **Java**: PMD (linting), spotbugs (static analysis), clang-format (formatting)

### Bazel File Formatting
```bash
# Format Bazel/Starlark files
bazel run //:buildifier.fix

# Check Bazel/Starlark formatting
bazel run //:buildifier.check
```

## Code Coverage

```bash
# Collect coverage across all languages (merged LCOV report)
bazel coverage --combined_report=lcov //...

# Render the combined report to HTML at ./coverage-html/ (hermetic lcov genhtml)
bazel run //tools/coverage:report

# Measure the C++ GCC build (gcov) instead of the default Clang LLVM coverage
bazel coverage --config=gcc_hermetic --combined_report=lcov //modules/cpp_library:cpp_library_test
```

C++ uses LLVM source-based coverage on the default Clang toolchain (no flags needed — wired in `.bazelrc`); Python capture requires `configure_coverage_tool` on the toolchain (already set); Go, Java (JaCoCo), and Rust work out of the box. In CI, the `coverage` job publishes the latest `main` report to GitHub Pages and comments coverage on PRs. Renderer and per-language wiring live in `tools/coverage/` and are gated behind the `coverage` bootstrap feature.

## Profiling

```bash
# List profilable targets (tags: profiling-cpu / profiling-mem)
bazel run //tools/profile -- --list

# Profile a CPU bench or a one-shot memory workload
bazel run //tools/profile -- //modules/{rust|go|cpp|python|java}_workloads:bench_matmul
bazel run //tools/profile -- //modules/{rust|go|cpp|python|java}_workloads:mem_retained_growth

# Batch, measure mode (real timings, no profiler), terminal flamegraph viewer
bazel run //tools/profile -- --all
bazel run //tools/profile -- //modules/{rust|go|cpp|python|java}_workloads:bench_matmul --measure
bazel run //tools/profile -- //modules/{rust|go|cpp|python|java}_workloads:bench_matmul --view

# System sampler (non-hermetic; needs host perf, kernel.perf_event_paranoid <= 2)
bazel run //tools/profile -- //modules/{rust|go|cpp|python|java}_workloads:bench_matmul --sampler=perf

# Options: --size N (WORKLOAD_N), --profile-seconds S, --scope PATTERN, --out DIR
```

Artifacts: `profile-out/<pkg>/<target>/{cpu|mem}/` — SVG flamegraph, `.folded` stacks, top-N text. The contract is language-independent: targets are discovered by tag (`profiling-cpu` = framework benches, `profiling-mem` = one-shot memory binaries); capture is per-language while the rendering spine and runner are shared (per-language capture matrix: README.md "Profiling"). Workload targets are gazelle-generated: add `# gazelle:profiling` to a package's BUILD and run `bazel run //:profile_gen` — sources under `benches/` and `mem/` map to tagged targets (opt-in; packages without the directive are never touched). Never quote timings from profile runs — use `--measure`. Example workloads live in `modules/{rust,go,cpp,python,java}_workloads`. Runner and rendering spine live in `tools/profile/`, gated behind the `profiling` bootstrap feature (requires rust + go + python toolchains).

## Publishing

```bash
# --include-pub-targets is required: artifacts | images | all

# Publish all modules (dev version, via mint orchestrator) — both tracks
bazel run //tools/publish:mint -- --mode dev --include-pub-targets all

# Publish a release from a branch — both tracks
bazel run //tools/publish:mint -- --mode release --branch main --include-pub-targets all

# Publish a single component set or module
bazel run //tools/publish:mint -- --mode dev --scope java_all --include-pub-targets all
bazel run //tools/publish:mint -- --mode dev --scope //modules/java_lib --include-pub-targets all

# Maven/PyPI artifacts only (skip OCI images)
bazel run //tools/publish:mint -- --mode dev --include-pub-targets artifacts

# OCI images only (skip Maven/PyPI)
bazel run //tools/publish:mint -- --mode dev --include-pub-targets images

# Dry run (print version plan)
bazel run //tools/publish:mint -- --mode dev --include-pub-targets all --dry-run

# Direct invocation (advanced — requires PUBLISH_VERSION env var)
PUBLISH_VERSION=1.2.3 bazel run --config=publish //modules/<name>:publish

# Publish tests
bazel test //tools/publish/tests/...
```

Version configuration: `.publish.toml`. Publish infrastructure: `tools/publish/`. See `tools/publish/README.md` for full details.

## Development Workflow

### Multi-Language Dependencies
- **Python**: Uses pip dependencies managed via `tools/python/requirements.in`
- **Rust**: External crates managed via `Cargo.toml` in `tools/rust/`
- **C++**: Dependencies via Bazel Central Registry (BCR) managed in `tools/cpp/cpp_3rd_party_dependencies.MODULE.bazel`
- **Java**: Maven dependencies configured in `tools/java/java_segment.MODULE.bazel` as `maven.install` `artifacts` parameter

### Regenerate Dependecies On Change
```bash
# Run following command after any Python dependency changes or Python version change
bazel run //tools/python:generate_requirements_lock.update

# Run following command after any Java Maven dependency changes or Java version change
bazel run @omniglot-bazel-starter_maven_dependencies//:pin

# Run following command after any Rust crate changes in tools/rust/Cargo.toml
# (note: `bazel sync` no longer exists — use fetch)
CARGO_BAZEL_REPIN=1 bazel fetch @crates//...

# Run following command after any Go dependency changes in go.mod
bazel run @rules_go//go -- mod tidy

# Run following command after adding or removing a module extension repo in any
# *.MODULE.bazel segment — syncs the use_repo() calls
bazel mod tidy
```

The four language commands above are the same ones the bootstrap tool runs after
scaffolding (`_LOCK_REFRESH_COMMANDS` in `tools/bootstrap/src/bootstrap/scaffolder.py`)
and the ones listed in README.md — keep all three in step. `bazel mod tidy` is not
part of that set.

Check `bazel mod tidy`'s diff before committing: it appends new repos to the *last*
`use_repo()` call for that extension, which here can land inside a `# --- BEGIN ... ---`
scaffold region — anything left in an `exclude` or unselected `feature:` region is
dropped from scaffolds. Move it out by hand.

### Debugging Toolchains
Use debug configurations to troubleshoot toolchain resolution:
```bash
# C++ toolchain debugging
bazel build --config=gcc_host_debug //modules/cpp_app

# Python toolchain debugging (local host interpreter)
bazel build --config=python_host_debug //modules/python_app
```

### Post Development Checks

After any substantial code changes, following steps to be taken to ensure code is ready for commit:
- **Bazel File Formatting**: run `bazel run //:buildifier.fix` if any Bazel files were modified (BUILD, .bzl, MODULE.bazel, WORKSPACE)
- **Source Code Formatting**: run automated formatting across all languages
- **Source Code Linting**: run automated linting with fail-on-violation mode enabled
- **Automated Testing**: run tests on all targets

All linting configurations are centralized in the root directory (`.ruff.toml`, `.clang-tidy`, `.rustfmt.toml`, etc.).