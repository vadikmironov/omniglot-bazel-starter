# CI workflows

`ci.yml` runs on every PR and push to `main`; `integration.yml` runs weekly;
`renovate.yml` runs the dependency bot every six hours.

## What runs when

| Tier | Jobs | Trigger |
|---|---|---|
| **0** Preflight | `buildifier.check`, `format.check` | PR + push |
| **1** Build & test | Linux x64 (hermetic Clang and GCC), macOS ARM64 (hermetic Clang), Windows x64 and ARM64 (MSVC) | PR + push |
| **1** Lint & coverage | clang-tidy, GCC `-fanalyzer`, PMD/SpotBugs/ruff/ty, the gazelle drift gates, the `MODULE.bazel.lock` freshness gate, coverage — Linux | PR + push |
| **2** Compilation modes | the same five platforms under `-c dbg` and `-c opt` | push to `main`, `workflow_dispatch`, or a PR labelled `ci-full-matrix` |
| **3** Weekly | remote toolchains (`gcc_remote`, `clang_remote`, `java_17_remote_corretto_jdk`), the profiling workloads, the bootstrap integration suite | Sundays 03:00 UTC, `workflow_dispatch` |

Preflight is split from the lint job so a formatting slip reports without waiting
on full analysis. The compilation-mode tier is post-merge because the code has
already passed the PR gate, and one run then maps to one squashed commit. Label a
PR `ci-full-matrix` to run tiers 0 to 2 on it.

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

## Renovate

`renovate.yml` runs Renovate self-hosted, every six hours and on
`workflow_dispatch`. The hosted Mend app cannot run Bazel, so its PRs leave
`MODULE.bazel.lock`, `go.sum` and `maven_install.json` stale and fail the lock
freshness gate. The self-hosted run executes the repo's own refresh commands as
`postUpgradeTasks` before each commit:

| Manager | Commands |
|---|---|
| `bazel-module`, `cargo` | `bazel mod deps --lockfile_mode=update` |
| `bazel-module`, `maven_install` artifacts (their own "maven artifacts" group) | `bazel run --repo_env=REPIN=1 @omniglot-bazel-starter_maven_dependencies//:pin`, then the lock refresh |
| `gomod` | `go mod tidy` with containerbase's Go; Bazel's `@rules_go//go` runner would pull the 2 GB LLVM toolchain, and go_deps is not in the module lock |
| `pep621` | none: Renovate runs `uv lock` itself |

The command allowlist lives in `renovate-global.json5`; the tasks live in
`/renovate.json`. A command that is not on the allowlist does not run.

### Setup

Do steps 1 to 4 before the workflow lands on `main`: the schedule starts with
the merge, and a run without the secrets fails at the token step.

1. Create a GitHub App (Settings, Developer settings, GitHub Apps) with these
   repository permissions: Commit statuses, Contents, Issues, Pull requests
   and Workflows as read and write; Administration, Checks and Dependabot
   alerts as read. Uncheck "Webhook active".
2. Install the App on this repository.
3. Create an environment named `renovate` (Settings, Environments) and limit
   its deployment branches to `main`. Add two secrets to it: `RENOVATE_APP_ID`
   (the App ID) and `RENOVATE_APP_PRIVATE_KEY` (a private key generated on
   the App page). The job binds to this environment, so only a run from
   `main` can mint the token; `workflow_dispatch` works from `main` only.
4. Remove this repository from the Mend Renovate app installation, and close
   its open `renovate/*` PRs and its Dependency Dashboard issue. Renovate
   matches branches and issues by author, so it treats the old ones as
   user-modified and opens a second dashboard.
5. Run once in dry-run mode and read the log before the schedule takes over:

```bash
gh workflow run renovate.yml -f dry-run=full -f log-level=debug
```

A full dry run still executes the `postUpgradeTasks`, so it validates the
Bazel commands and the tool install; it only skips creating branches and PRs.

The App's commits trigger CI like any other push, which the workflow's own
`GITHUB_TOKEN` would not. The token reaches every task command through
Renovate's git environment, so a compromised dependency that runs code during
`bazel mod deps` could use it: the environment above limits the blast radius
to what a run from `main` can do, and one required approving review on `main`
stops the App from merging its own PRs.
