# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

This is a Bazel-based polyglot monorepo demonstrating multi-language development with Python, Rust, C++, and Java. The repository uses Bazel's module system (`MODULE.bazel`) and is organized into language-specific modules under the `modules/` directory.

### Key Components

- **Bazel Configuration**: Uses `MODULE.bazel` for dependency management with language-specific segments
- **Toolchain Management**: Hermetic toolchains for all languages with configurable platform support
- **Linting/Formatting**: Integrated via `aspect_rules_lint` with language-specific tools
- **Module Structure**: Each language has example applications and libraries with external dependencies

## Build Commands

### Basic Build and Test
```bash
# Build all targets
bazel build //...

# Test all targets
bazel test //...

# Build specific modules

# Python applications
bazel build //modules/python_app
bazel build //modules/python_app_with_ext_dep

# Rust applications
bazel build //modules/rust_app
bazel build //modules/rust_app_with_ext_dep
bazel build //modules/rust_lib:rust_lib_test

# C++ applications
bazel build //modules/cpp_app
bazel build //modules/cpp_app_with_ext_dep

# Java applications
bazel build //modules/java_app
bazel build //modules/java_app_with_ext_dep

# Libraries
bazel build //modules/python_lib:python_lib
bazel build //modules/rust_lib:rust_lib
bazel build //modules/cpp_library:cpp_library
bazel build //modules/java_lib:java_lib
```

### Language-Specific Toolchain Selection
```bash
# C++ default is the hermetic LLVM/Clang toolchain (no flag needed).

# C++ with hermetic GCC (f0rmiga/gcc-toolchain, pinned GCC 15.2.0)
bazel build --config=gcc_hermetic //modules/cpp_app

# C++ hermetic GCC toolchain resolution debugging
bazel build --config=gcc_hermetic_debug //modules/cpp_app

# C++ with GCC host compiler (non-hermetic, system gcc)
bazel build --config=gcc_host //modules/cpp_app:main

# C++ with Clang host compiler (non-hermetic, system clang)
bazel build --config=clang_host //modules/cpp_app:main

# Python with local host interpreter (3.13)
bazel build --config=python3_13_host //modules/python_app:main

# Python toolchain debugging
bazel build --config=python_toolchain_debug //modules/python_app:main
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
# Format Bazel/Starlark files (Mac/Linux)
bazel run //:buildifier.fix

# Check Bazel/Starlark formatting (Mac/Linux)
bazel run //:buildifier.check

# Format Bazel/Starlark files (Windows)
tools\buildifier.bat fix

# Check Bazel/Starlark formatting (Windows)
tools\buildifier.bat check
```

## Testing

### Running Tests
```bash
# All tests
bazel test //modules/...

# Language-specific tests
bazel test //modules/python_lib/tests/...
bazel test //modules/rust_lib:rust_lib_test
bazel test //modules/cpp_library:cpp_library_test
bazel test //modules/java_lib:java_lib_test
```

### Test Output
Tests are configured to show errors only (`--test_output=errors` in .bazelrc).

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

# Profile a CPU bench (criterion + pprof) or a memory workload (jemalloc heap)
bazel run //tools/profile -- //modules/rust_workloads:bench_matmul
bazel run //tools/profile -- //modules/rust_workloads:mem_retained_growth

# Batch, measure mode (real timings, no profiler), terminal flamegraph viewer
bazel run //tools/profile -- --all
bazel run //tools/profile -- //modules/rust_workloads:bench_matmul --measure
bazel run //tools/profile -- //modules/rust_workloads:bench_matmul --view

# System sampler (non-hermetic; needs host perf, kernel.perf_event_paranoid <= 2)
bazel run //tools/profile -- //modules/rust_workloads:bench_matmul --sampler=perf

# Options: --size N (WORKLOAD_N), --profile-seconds S, --scope PATTERN, --out DIR
```

Artifacts: `profile-out/<pkg>/<target>/{cpu|mem}/` — SVG flamegraph, `.folded` stacks, top-N text. Targets are discovered by tag (`profiling-cpu` = criterion benches, `profiling-mem` = one-shot memory binaries); Rust example workloads live in `modules/rust_workloads`. Never quote timings from profile runs — use `--measure`. Memory profiling is Linux-only (jemalloc_pprof upstream limit); the `mem_*` targets carry `target_compatible_with` and skip automatically on other platforms. Runner and rendering spine live in `tools/profile/`, gated behind the `profiling` bootstrap feature (requires rust + go + python toolchains).

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
```

### Key Configuration Files
- `.bazelrc`: Build configurations and toolchain settings
- `MODULE.bazel`: Main module definition with language-specific includes
- `tools/`: Language-specific build definitions and toolchain configurations

### Debugging Toolchains
Use debug configurations to troubleshoot toolchain resolution:
```bash
# C++ toolchain debugging
bazel build --config=gcc_host_debug //modules/cpp_app:main

# Python toolchain debugging (local 3.13)
bazel build --config=python3_13_host_debug //modules/python_app:main
```

### Post Development Checks

After any substantial code changes, following steps to be taken to ensure code is ready for commit:
- **Bazel File Formatting**: run `bazel run //:buildifier.fix` (Mac/Linux) or `tools\buildifier.bat fix` (Windows) if any Bazel files were modified (BUILD, .bzl, MODULE.bazel, WORKSPACE)
- **Source Code Formatting**: run automated formatting across all languages
- **Source Code Linting**: run automated linting with fail-on-violation mode enabled
- **Automated Testing**: run tests on all targets

All linting configurations are centralized in the root directory (`.ruff.toml`, `.clang-tidy`, `.rustfmt.toml`, etc.).