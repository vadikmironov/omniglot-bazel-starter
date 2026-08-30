# CI workflows

`ci.yml` runs on every PR and push to `main`; `integration.yml` runs weekly.

## What runs when

| Tier | Jobs | Trigger |
|---|---|---|
| Preflight | `buildifier.check`, `format.check` | PR + push |
| Build & test | Linux (hermetic Clang and GCC), macOS (hermetic Clang), Windows (MSVC) | PR + push |
| Lint & coverage | clang-tidy, GCC `-fanalyzer`, PMD/SpotBugs/ruff/ty, the gazelle drift gates, the `MODULE.bazel.lock` freshness gate, coverage — Linux | PR + push |
| Compilation modes | the same four platforms under `-c dbg` and `-c opt` | push to `main`, `workflow_dispatch` |
| Weekly | remote toolchains (`gcc_remote`, `clang_remote`, `java_17_remote_corretto_jdk`), the profiling workloads, the bootstrap integration suite | Sundays 03:00 UTC, `workflow_dispatch` |

Preflight is split from the lint job so a formatting slip reports without waiting
on full analysis. The compilation-mode tier is post-merge because the code has
already passed the PR gate, and one run then maps to one squashed commit.

## Platform scope

Linux and macOS build and test `//...`. Windows is scoped to `//modules/...`:
everything under `//tools/...` resolves clang-tidy, clang-format and
llvm-symbolizer from the hermetic LLVM, which has no Windows build
([toolchains_llvm#4](https://github.com/bazel-contrib/toolchains_llvm/issues/4)),
so C++/Java lint and format are Linux/macOS only.

Two further exclusions on Windows:

- the profiling workloads, by tag — gperftools has no Windows build and memray
  ships no Windows wheels
- `//modules/go_app_with_cgo_dep` — cgo parses GCC-style compiler diagnostics, so
  rules_go does not accept `msvc-cl`

The weekly remote-toolchain jobs are scoped per toolchain: the C++ ones cover the
C++ modules, since the remote compilers link against the host glibc, while the
remote JDK covers `//...`.

## Other behaviour

- BuildBuddy remote caching speeds up both CI and local builds, each configured
  with its own API key. Fork PRs have no access to the secret and run uncached
- Stale runs are cancelled when new commits are pushed
- Any job can be triggered manually via `workflow_dispatch`
- The `coverage` job publishes the latest `main` report to GitHub Pages and
  comments coverage on PRs
- A failing weekly run opens or updates a single issue labelled `ci-weekly`; none
  of its jobs gate a merge
