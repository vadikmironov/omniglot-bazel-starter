# omniglot-bazel-starter

> A bzlmod-based Bazel polyglot monorepo starter — speaks Python, Rust, C++, Java, and Go out of the box.

An opinionated template for teams standing up a new Bazel monorepo and immediately hitting the question *"…but how do we do this in every language at once?"*. Fork it, prune the languages you don't need, and keep the patterns that stayed.

## What's included

- **Hermetic toolchains** for every language, with swappable variants (GCC/Clang, Corretto 17/21/25, Python 3.13, …)
- **Cross-language interop** — working examples of C++ extensions embedded in Python, and Python runtimes bootstrapped from C++
- **Unified lint / format** pipeline via [`aspect_rules_lint`](https://github.com/aspect-build/rules_lint) — ruff, ty, clippy, clang-tidy, clang-format, PMD, spotbugs, rustfmt, gofumpt, buildifier
- **Publishing infrastructure** — a Gazelle extension auto-generates `:publish` targets for Maven / PyPI / generic registries (Artifactory, Nexus, Gitea)
- **Cross-platform CI** — Linux, macOS arm64, Windows — with [BuildBuddy](https://www.buildbuddy.io/) remote caching
- **`bzlmod`-first** — `MODULE.bazel` is segmented by language for easy pruning
- **One-command bootstrap** — scaffold a brand-new repo with only the languages and features you pick via an interactive [`bazel run //tools/bootstrap`](#bootstrapping-a-new-repo)

## Repo shape at a glance

Each supported language follows the same three-part pattern so you see *patterns*, not one-offs:

- `modules/<lang>_app` — a minimal app
- `modules/<lang>_lib` — a library with tests
- `modules/<lang>_app_with_ext_dep` — the same app pulling an external dependency

One hop from any *"how do I do X in `<lang>`?"* question to a working example. The per-language sections below go deeper on each ruleset, toolchain story, external-dependency management, lint pipeline, and interop examples — read the one you care about.

## Bootstrapping a new repo

This repository is itself the template. The bootstrap tool copies a *filtered* slice of it into a new directory — only the languages and features you pick — rewrites the module name throughout, and `git init`s the result.

```bash
# Interactive — prompts for every choice
bazel run //tools/bootstrap

# Review mode — show a diff and confirm before overwriting any file that
# differs from the starter, and inspect each path before pruning on re-bootstrap
bazel run //tools/bootstrap -- --review
```

It walks you through:

- **Target directory** and **repository name** — the module name is rewritten everywhere
- **Languages** — any subset of Python, Rust, C++, Java, Go
- **Optional features** — `lint` (the full static-analysis pipeline), `remote caching` and `publish`; each auto-adds the languages it requires
- **Code directory** — the top-level dir that holds your modules/services/apps

After scaffolding it can refresh dependency lock files and run per-feature finalizers (`lint_gen`, `publish_gen`), then formats the generated Bazel files. The summary prints your `cd` / `bazel build //...` next steps.

**Re-bootstrapping:** point the tool at an already-bootstrapped repo and it detects the existing selection (from the `.omniglot_bootstrap.toml` marker it writes), refreshes the starter baseline, and lets you add or drop languages/features. Dropped owners are pruned (with confirmation), while edits you made inside user-managed regions are carried forward.

Full guide — every prompt, re-bootstrap, and `--review` — in [`tools/bootstrap/README.md`](tools/bootstrap/README.md); manifest format and extension internals in [`tools/bootstrap/AGENTS.md`](tools/bootstrap/AGENTS.md).

## Python

[rules_python](https://github.com/bazelbuild/rules_python/blob/main/README.md) documentation is available [here](https://rules-python.readthedocs.io/en/latest/index.html). Full integration with pip is supported and this repo provides an example of a binary with external dependencies [here](modules/python_app_with_ext_dep/README.md). Monorepo wide pip based repository available in any module, but it is also possible to register several different set of requirements (requirements_dev for example).

[rules_python](https://github.com/bazelbuild/rules_python/blob/main/README.md) do not offer yet an ability to manage virtual environments which might be useful for development setup. This has been added via separate [rules_uv](https://github.com/theoremlp/rules_uv). [rules_python](https://github.com/bazelbuild/rules_python/blob/main/README.md) also have a [ticket](https://github.com/bazelbuild/rules_python/issues/1975) to integrate uv and uv based toolchains, but it is yet marked as experimental.

[rules_python](https://github.com/bazelbuild/rules_python/blob/main/README.md) in general allow flexible [toolchain configuration](https://rules-python.readthedocs.io/en/latest/toolchains.html#). It is also possible to use a locally installed python toolchain and this is documented [here](https://rules-python.readthedocs.io/en/latest/toolchains.html#local-toolchain). The [local toolchain definition](tools/python/python_segment.MODULE.bazel) can be selected via `.bazelrc` build flags and [Bazel --config command line option](https://bazel.build/run/bazelrc#config) similar to [C++](#cc). **Note:** [rules_python](https://github.com/bazelbuild/rules_python/blob/main/README.md) are using pre-built Python toolchains [hosted here](https://github.com/astral-sh/python-build-standalone/releases) and automatically map a toolchain version argument to a [specific Python toolchain version](https://github.com/bazelbuild/rules_python/blob/main/python/versions.bzl).

[rules_python](https://github.com/bazelbuild/rules_python/blob/main/README.md) do not provide any development tools like formatting and linting out of the box. This repository makes use of [aspect_rules_lint](https://github.com/aspect-build/rules_lint/blob/main/README.md) in order to provide consistent [formatting](https://github.com/aspect-build/rules_lint/blob/main/docs/formatting.md) and [linting](https://github.com/aspect-build/rules_lint/blob/main/docs/linting.md) experience. Static type checking with Mypy is also supported via standalone [rules_mypy](https://github.com/theoremlp/rules_mypy) which provide a seamless integration with python Bazel targets.

[Python C extension modules](https://docs.python.org/3/extending/extending.html) are supported via `cc_shared_library` combined with `py_library`, using facilities added under [this rules_python C extension support request](https://github.com/bazel-contrib/rules_python/issues/824). This repository includes an [example extension module](modules/cpp_py_ext_module/README.md) that wraps a C++ library for Python consumption. Alternatively, there is a [pybind11 rules](https://github.com/pybind/pybind11_bazel) implementation for Bazel which adds dedicated `pybind_extension`/`pybind_library` rules.

## Rust

[rules_rust](https://github.com/bazelbuild/rules_rust/blob/main/README.md) provides an all-in-one development experience for Bazel enabled monorepos. Official documentation is available [here](https://bazelbuild.github.io/rules_rust/rules.html), but [Rust Project Primer](https://rustprojectprimer.com/build-system/bazel.html) provides a good overview + set of links to Bazel and Rust resources. [This blog post nicely summarizes](https://mmapped.blog/posts/17-scaling-rust-builds-with-bazel) why Bazel as a build tool was a good choice for Rust based ecosystem.

When configuring rules_rust, you need to specify a Rust toolchain version. The full list of available versions can be found [here](https://releases.rs/#rust-versions). [rust_register_toolchains](https://bazelbuild.github.io/rules_rust/#specifying-rust-version) provides a flexibility to define both stable and nightly versions should one wish to use nightly in CI settings.

Rust examples showcase rust binary and library builds, as well as a [binary with crate dependency](modules/rust_app_with_ext_dep/README.md). These examples are based on an adapted version of [rules_rust examples](https://github.com/bazelbuild/rules_rust/tree/main/examples).

[rules_rust](https://github.com/bazelbuild/rules_rust/blob/main/README.md) also provides rustfmt (formatting), clippy (linting), and rustdoc (documentation) rules. `rustfmt` is integrated via [aspect_rules_lint](https://github.com/aspect-build/rules_lint/blob/main/README.md) for consistent formatting usage, while for linting `clippy` is supported via [aspect_rules_lint](https://github.com/aspect-build/rules_lint/blob/main/examples/rust/tools/lint/linters.bzl) with an option to have it standalone via [rules_rust](https://bazelbuild.github.io/rules_rust/rust_clippy.html).

Unlike [rules_python](https://github.com/bazelbuild/rules_python/blob/main/README.md), [rules_rust](https://github.com/bazelbuild/rules_rust/blob/main/README.md) does not allow to use locally installed Rust toolchain yet. This has been [reported in the rules_rust issue tracker](https://github.com/bazelbuild/rules_rust/issues/2275), but there is no activity yet. This issue may in particular affect setups where building local toolchain is not possible or not feasible due to a combination of available compilers and OS.

### Rust <> C++ Interop

There are three main approaches to Rust/C++ interop, each with different trade-offs. [CXX](https://cxx.rs/) is the industry standard for safe bidirectional interop — it uses a `#[cxx::bridge]` macro to define the FFI boundary and generates both C++ headers and Rust glue with zero-cost abstractions. Types like `String`, `Vec`, `UniquePtr`, and `Box` cross the boundary idiomatically, and no `unsafe` code is required on either side. CXX is [production-proven at Chromium scale](https://google.github.io/comprehensive-rust/chromium/interoperability-with-cpp/using-cxx-in-chromium.html) and available on [BCR](https://registry.bazel.build/modules/cxx.rs) as `bazel_dep(name = "cxx.rs")`. Bazel integration requires a custom `rust_cxx_bridge` rule to run the code generator — the [CXX repository](https://github.com/dtolnay/cxx) provides a reference implementation.

For consuming existing C/C++ headers from Rust, [bindgen](https://rust-lang.github.io/rust-bindgen/) auto-generates Rust FFI bindings from header files. [rules_rust](https://github.com/bazelbuild/rules_rust/blob/main/README.md) provides a dedicated [`rust_bindgen_library`](https://bazelbuild.github.io/rules_rust/rust_bindgen.html) rule that wraps the generation and produces a ready-to-use `rust_library`. This works well for large or frequently-changing C APIs but produces `unsafe` bindings and has limited C++ support (no templates or classes). For the reverse direction — exposing a Rust library to C++ — [`rust_static_library`](https://bazelbuild.github.io/rules_rust/rust.html) produces a static archive with `CcInfo`, so any `cc_binary` can depend on it directly. Header generation can be done via [cbindgen](https://github.com/mozilla/cbindgen) (no official Bazel rule yet, [tracked here](https://github.com/bazelbuild/rules_rust/issues/381)) or through CXX bridge definitions. Working BUILD examples for both directions are available in [rules_rust/examples/ffi](https://github.com/bazelbuild/rules_rust/tree/main/examples/ffi).

One gotcha to watch for: C++ static libraries need `-fPIC` when linking with Rust PIE executables, which may require `build --copt -fPIC` in `.bazelrc` or per-target `copts`. When using CXX, the `cxxbridge-cmd` tool version must exactly match the `cxx` crate version — pin both via lockfiles.

### Rust <> Python Interop

[PyO3](https://pyo3.rs/main/index.html) and [rules_pyo3](https://github.com/abrisco/rules_pyo3) provide Rust/Python interop with Bazel integration.

## C/C++

[rules_cc](https://github.com/bazelbuild/rules_cc/blob/main/README.md) are Bazel native implementation of C and C++ build rules in Starlark. Documentation is available [here](https://bazel.build/reference/be/overview#language-specific-native-rules), but in comparison with other rules documentation is very frugal to say the least. Worth noting that according to the [Bazel roadmap](https://bazel.build/about/roadmap#migration-android), rules_cc are expected to get a lot of attention in 2025 to complete the migration to the native Starlark implementation.

Unlike [Python](#python) and [Rust](#rust) there is no clear majority with regards to an external dependency/package management solution. Bazel C++ has several ways to manage third-party dependencies. [The README.md in corresponding C++ example](modules/cpp_app_with_ext_dep/README.md) explores a Bazel-native option based on [Bazel Central Registry (BCR)](https://registry.bazel.build/), but also provides further overview over other potential ways.

C++ support for toolchains is very robust with rich [platforms](https://bazel.build/extending/platforms) and [toolchains](https://bazel.build/extending/toolchains) framework. [Hermetic LLVM based toolchain](https://github.com/bazel-contrib/toolchains_llvm/blob/master/README.md) is the most actively developed one and enabled by default for any C++ targets in this repository. A second [hermetic GCC toolchain](https://github.com/f0rmiga/gcc-toolchain) (pinned GCC 15.2.0) is wired in as an opt-in alternative, selected with `--config=gcc_hermetic` (see [`.bazelrc`](.bazelrc)). Also there is an example of non-hermetic system toolchains which is further documented [here](tools/cpp/toolchains/README.md). Toolchain resolution is documented [here](https://bazel.build/extending/toolchains#toolchain-resolution) and for this repository there are [examples of configuration sets](.bazelrc) which are documented [here](https://bazel.build/run/bazelrc#config) in details.

[aspect_rules_lint](https://github.com/aspect-build/rules_lint/blob/main/README.md) is setup with [clang-format based C++ formatting](https://clang.llvm.org/docs/ClangFormat.html) and [clang-tidy based C++ linting](https://clang.llvm.org/extra/clang-tidy/). Both are coming from [hermetic LLVM based toolchain](https://github.com/bazel-contrib/toolchains_llvm) which is also registered as a default platform for all C++ examples. clang-tidy is build-toolchain-independent (it parses sources with its own Clang frontend), so it lints regardless of the selected compiler; the GCC-side analog is GCC's built-in [`-fanalyzer`](https://gcc.gnu.org/onlinedocs/gcc/Static-Analyzer-Options.html), wired as `--config=gcc_analyzer` (scoped to first-party sources, `-Werror`-gated).

## Java

[rules_java](https://github.com/bazelbuild/rules_java/blob/main/README.md) provides Java build rules for Bazel. Documentation is available [here](https://bazel.build/reference/be/java), though like C++ rules, it can be sparse in places. The rules are well-maintained and receive regular updates as part of Bazel's core language support.

External dependencies are managed via [rules_jvm_external](https://github.com/bazel-contrib/rules_jvm_external), which provides Maven artifact resolution and lockfile support. Dependencies are declared in a central `maven.install()` block and referenced using the `@maven//:group_id_artifact_id` pattern. After adding or updating dependencies in `java_segment.MODULE.bazel`, regenerate the lockfile with `REPIN=1 bazel run @omniglot-bazel-starter_maven_dependencies//:pin`. This repo includes examples of [a simple Java binary](modules/java_app/BUILD) and [a binary with Maven dependencies](modules/java_app_with_ext_dep/BUILD) including Log4j and jsoup.

[rules_java](https://github.com/bazelbuild/rules_java/blob/main/README.md) provides flexible [toolchain configuration](https://github.com/bazelbuild/rules_java/blob/main/docs/toolchains.md) with remote Azul Zulu JDKs available by default. This repository also includes custom [Amazon Corretto toolchain configurations](tools/java/toolchains/README.md) demonstrating both remote (auto-downloaded) and local (pre-installed) JDK setups. Toolchain selection is controlled via `--java_runtime_version` and `--java_language_version` flags, with convenience configs available in [.bazelrc](.bazelrc) (e.g., `--config=java_17_remote_corretto_jdk`).

[aspect_rules_lint](https://github.com/aspect-build/rules_lint/blob/main/README.md) is configured with [PMD](https://pmd.github.io/) for linting and [SpotBugs](https://spotbugs.github.io/) for static analysis. Formatting uses [clang-format](https://clang.llvm.org/docs/ClangFormat.html) instead of the default google-java-format, which has [notoriously limited configuration options](https://jqno.nl/post/2024/08/24/why-are-there-no-decent-code-formatters-for-java/).

For unit testing, this repository provides custom macros for JUnit 5 (Jupiter) support in [tools/java/testing](tools/java/testing). The `java_junit5_test` macro wraps `java_test` to run tests via the JUnit Platform ConsoleLauncher, automatically including all required JUnit 5 dependencies. The `java_test_suite` macro creates individual test targets for each source file, enabling better parallelization on RBE, and aggregates them into a test suite. Both macros are derived from [rules_jvm](https://github.com/bazel-contrib/rules_jvm). See [java_lib](modules/java_lib/BUILD) for a usage example.

## Go

[rules_go](https://github.com/bazel-contrib/rules_go/blob/master/README.rst) provides Go build rules for Bazel. Comprehensive documentation is available [here](https://github.com/bazel-contrib/rules_go/blob/master/docs/go/core/rules.md), with detailed toolchain documentation [here](https://github.com/bazel-contrib/rules_go/blob/master/go/toolchains.rst). [Gazelle](https://github.com/bazel-contrib/bazel-gazelle) is used for Go module dependency management via its `go_deps` extension.

External dependencies are managed via `go.mod` and Gazelle's `go_deps` extension. To add or update dependencies, use the wrapped Go command: `bazel run @rules_go//go -- get github.com/package@version`. This updates `go.mod`, `go.sum`, and runs `bazel mod tidy` automatically. Dependencies are then available via their repository names (e.g., `@com_github_stretchr_testify//assert`). See [go_segment.MODULE.bazel](tools/go/go_segment.MODULE.bazel) for dependency configuration details.

[rules_go](https://github.com/bazel-contrib/rules_go/blob/master/README.rst) provides flexible toolchain configuration with remote SDK downloads available by default. This repository also includes a custom [local Go SDK module extension](tools/go/toolchains/local_go_sdk.bzl) for using a pre-installed Go SDK. See [go_segment.MODULE.bazel](tools/go/go_segment.MODULE.bazel) for an example of both local and remote toolchain configuration, with convenience configs available in [.bazelrc](.bazelrc).

[aspect_rules_lint](https://github.com/aspect-build/rules_lint/blob/main/README.md) is configured with [gofumpt](https://github.com/mvdan/gofumpt) for formatting (a stricter superset of gofmt). Static analysis is provided via [nogo](https://github.com/bazel-contrib/rules_go/blob/master/go/nogo.rst), which integrates Go's built-in vet tool and custom analyzers directly into the build process, catching issues at compile time rather than as a separate lint step.

## Developer Setup

### Install Bazelisk

Bazelisk is the only Bazel binary you need — it reads `.bazelversion` and fetches the matching Bazel release on demand. The installer verifies each download's SHA256 and chooses an install mode automatically:

```bash
# Auto: system install (apt/.deb) when root or passwordless sudo is available,
# otherwise a no-sudo install into ~/.local/bin
tools/setup/install_bazelisk.sh

# Force a no-sudo user install (~/.local/bin, PATH wired into your shell rc)
tools/setup/install_bazelisk.sh --user

# Force a system-wide install (apt/.deb; prompts for sudo if needed)
tools/setup/install_bazelisk.sh --system
```

The installer script is Linux-only; on macOS use `brew install bazelisk`, on Windows `choco install bazelisk` (or `npm install -g @bazel/bazelisk` on any platform). Run `bazel version` to verify (restart your shell first if the installer added `~/.local/bin` to your PATH). Pin a specific launcher version with `BAZELISK_VERSION=v1.25.0`.

### Common Commands

```bash
# List runnable targets — apps, buildifier, venv (plain `//...` lists everything)
bazel query 'kind("(py|cc|go|java|rust)_binary|buildifier|_venv", //...)'

# Build / test everything
bazel build //...
bazel test //...                     # excludes lint tests — run lint separately

# Format source (all languages), then Bazel/Starlark files
bazel run //:buildifier.fix          # Windows: tools\buildifier.bat fix
bazel run //:format

# Lint: (re)generate per-target lint rules, then run them as tests
bazel run //:lint_gen                # preview without writing: -- -mode diff
bazel test --test_tag_filters=lint //...

# Regenerate dependency locks after editing a manifest
bazel run //tools/python:generate_requirements_lock.update            # Python — tools/python/requirements.in
REPIN=1 bazel run @omniglot-bazel-starter_maven_dependencies//:pin    # Java   — Maven artifacts
CARGO_BAZEL_REPIN=1 bazel sync --only=crates                          # Rust   — tools/rust/Cargo.toml
bazel run @rules_go//go -- mod tidy                                   # Go     — go.mod / go.sum
```

### Remote Cache (BuildBuddy)

Local builds can use a BuildBuddy remote cache for faster builds (bring your own API key):

```bash
# 1. Copy the template and add your API key
cp user.bazelrc.template user.bazelrc
# Edit user.bazelrc — uncomment and set your BuildBuddy API key

# 2. Build with remote cache enabled
bazel build --config=remote-cache //modules/...
bazel test --config=remote-cache //modules/...
```

The `user.bazelrc` file is gitignored. See `user.bazelrc.template` for details.

### Pre-commit Hooks

Fast local formatting and linting checks (< 2s, no Bazel startup):

```bash
# Create/update .venv with all dev tools including pre-commit (one-time)
bazel run //tools/python:generate_virtual_env

# Install hooks (one-time)
.venv/bin/pre-commit install

# Hooks run automatically on git commit
# Run manually on all files:
.venv/bin/pre-commit run --all-files
```

**Hooks configured:** buildifier (Bazel files), ruff (Python), clang-format (Java/C++).

### CI Workflow

- Every PR and push to `main` runs the full gate: build + test on Linux (hermetic Clang and GCC) and macOS (hermetic Clang), plus the lint phase
- **Windows** builds are currently disabled
- BuildBuddy remote caching speeds up both CI and local builds (each configured with its own API key)
- Stale CI runs are automatically cancelled when new commits are pushed
- Trigger a manual run via GitHub Actions `workflow_dispatch`
- The `coverage` job publishes the latest `main` report to GitHub Pages and comments coverage on PRs (see [Code Coverage](#code-coverage))

### Code Coverage

Coverage works across all languages through `bazel coverage`, merged into a single LCOV report and rendered to HTML by the hermetic lcov `genhtml` (no system `lcov` needed):

```bash
# 1. Collect coverage across the repo (merged LCOV)
bazel coverage --combined_report=lcov //...

# 2. Render the HTML report to ./coverage-html/, then open index.html
bazel run //tools/coverage:report
```

- **C++** uses LLVM source-based coverage on the default Clang toolchain; add `--config=gcc_hermetic` to measure the GCC build (gcov) instead.
- In CI, the `coverage` job publishes the latest `main` report to **GitHub Pages** and posts the overall line coverage on pull requests, along with the delta against the current `main` baseline. Enable Pages with source **"GitHub Actions"** (Settings → Pages).

**TeamCity (optional self-hosted sink):** the same LCOV / `genhtml` output feeds a private TeamCity instance (the free self-hosted Professional edition):

1. Run `bazel coverage --combined_report=lcov //...` then `bazel run //tools/coverage:report` as a build step.
2. Publish `coverage-html/` as a build artifact and add a **report tab** with start page `index.html`.
3. Emit the coverage statistic so TeamCity tracks the trend and can gate on a threshold: `##teamcity[buildStatisticValue key='CodeCoverageL' value='<pct>']`.
4. Add the **Commit Status Publisher** build feature to post the coverage build status back to the GitHub PR.

### Profiling

CPU and memory profiling driven by tagged benchmark targets, rendered to flamegraphs by a fully hermetic toolchain (in-process capture → pprof → folded stacks → inferno SVG — no system tools needed). Rust example workloads live in `modules/rust_workloads`:

```bash
# List profilable targets (tags: profiling-cpu / profiling-mem)
bazel run //tools/profile -- --list

# Profile a criterion bench: SVG flamegraph + top-N table per bench function
bazel run //tools/profile -- //modules/rust_workloads:bench_matmul

# Profile a one-shot memory workload (jemalloc heap profile)
bazel run //tools/profile -- //modules/rust_workloads:mem_retained_growth

# Real benchmark timings — no profiler attached
bazel run //tools/profile -- //modules/rust_workloads:bench_matmul --measure

# Browse the captured stacks in the terminal (flamelens TUI)
bazel run //tools/profile -- //modules/rust_workloads:bench_matmul --view
```

Artifacts land in `profile-out/<package>/<target>/{cpu|mem}/` as self-contained `.svg` flamegraphs (click-to-zoom, Ctrl-F search — open in any browser), `.folded` stacks, and `top.txt` summaries. `--all` profiles every discovered target; `--size N` rescales a workload (exported as `WORKLOAD_N`); `--profile-seconds S` adjusts capture length.

To profile your own code, tag a criterion-bench `rust_binary` with `profiling-cpu`, or a one-shot binary with `profiling-mem` (jemalloc global allocator + `jemalloc_pprof` dump — see `modules/rust_workloads/mem/prof_dump.rs` for the shim).

- **Profile runs are not measurement runs.** Quote timings only from `--measure` runs; profiling distorts them.
- **The memory story is jemalloc's.** Memory workloads link jemalloc (the heap profiler lives in the allocator), so allocator observations — fragmentation especially — describe jemalloc, not glibc malloc. Heap profiles record *live* allocations at dump time, sampled every 32 KiB by default (`MALLOC_CONF` env overrides); transient churn shows up through its allocation sites, not its peak volume.
- **Memory profiling is Linux-only** (`jemalloc_pprof` supports only Linux); the `mem_*` targets are constrained accordingly and skip automatically elsewhere. CPU profiling works on Linux and macOS.

## Publishing

Artifact publishing is managed by `mint`, a publish orchestrator that handles version resolution via git tags and `.publish.toml`. Supports Artifactory, Nexus, and Gitea registries.

```bash
# Publish all modules (dev version)
bazel run //tools/publish:mint -- --mode dev

# Publish a release
bazel run //tools/publish:mint -- --mode release --branch main

# Publish a single component set
bazel run //tools/publish:mint -- --mode dev --scope java_all

# Dry run (print version plan without building)
bazel run //tools/publish:mint -- --mode dev --dry-run

# Direct invocation (advanced — requires PUBLISH_VERSION)
PUBLISH_VERSION=1.2.3 bazel run --config=publish //modules/java_lib:publish
```

Configuration is via `.publish.toml` (version schemas, component grouping), `.bazelrc` flags (registry URL), and `~/.netrc` credentials. See [tools/publish/README.md](tools/publish/README.md) for full setup.

`:publish` targets for modules that follow the canonical BUILD convention (rule name matches package basename) are auto-generated by a Gazelle extension — run `bazel run //:publish_gen` to (re)emit them. CI enforces convergence via `-publish_strict`. See [Auto-Generating `:publish` Targets](tools/publish/README.md#auto-generating-publish-targets-gazelle) for details.

## Contributing
Contributions and feedback are welcome! Feel free to open a pull request for any suggestions or improvements.

## Roadmap

- Rust ⇄ C/C++ interop example with working BUILD targets
- Python extension module written in Rust (PyO3)
- Possible additions: `rules_kotlin`, `rules_csharp`

## License

Released under the MIT License — see [LICENSE](LICENSE).
