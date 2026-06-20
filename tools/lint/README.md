# Lint Infrastructure

Per-target lint coverage as Bazel test rules, generated automatically by a
Gazelle extension.

## Quick Start

```bash
# 1. Generate or refresh lint_test targets across the repo
bazel run //:lint_gen

# 2. Run all lint tests
bazel test --test_tag_filters=lint //...

# 3. Preview what lint_gen would change without applying
bazel run //:lint_gen -- -mode diff
```

## How It Works

`//:lint_gen` is a Gazelle driver that walks every BUILD file, identifies
canonical source rules (`cc_*`, `rust_*`, `java_*`, `py_*`), and emits a
sibling lint_test target per rule, tagged `lint`. Python (ruff), C++ (clang-tidy)
and Java (PMD, SpotBugs) run via `aspect_rules_lint` aspects; Rust (clippy) runs
via native `rules_rust` — see [Rust clippy](#rust-clippy) below.

| Source rule kinds | Generated kind | Tool | Test name suffix |
|-------------------|----------------|------|------------------|
| `cc_binary`, `cc_library` | `clang_tidy_test` | clang-tidy (`aspect_rules_lint`) | `.lint` |
| `rust_binary`, `rust_library`, `rust_test` | `clippy_test` | clippy (native `rules_rust`) | `.lint` |
| `java_binary`, `java_library` | `pmd_test` | PMD (`aspect_rules_lint`) | `.pmd_lint` |
| `java_binary`, `java_library` | `spotbugs_test` | SpotBugs (`aspect_rules_lint`) | `.spotbugs_lint` |
| `py_binary`, `py_library` | `ruff_test` | ruff (`aspect_rules_lint`) | `.lint` |

Java emits two lint tests per source rule (PMD + SpotBugs); the suffixes keep
their names distinct. `cc_test`, `java_test`, and `py_test` stay outside their
source allowlists; `rust_test` is included — native `rust_clippy` lints test
crates like any other (its `clippy_test` is `testonly` so it can depend on the
`rust_test` source).

### Rust clippy

Rust does not use `aspect_rules_lint`. After 2.5.2 aspect_rules_lint moved clippy
into the separate `aspect_rules_lint_rust` module, which sources `rules_rust` from
`rules_rs`; against our BCR `rules_rust` targets that module's clippy aspect finds
no matching `CrateInfo` and silently passes — a false green (see
[aspect-build/rules_lint#879](https://github.com/aspect-build/rules_lint/issues/879)).

Instead `clippy_test` ([`linters.bzl`](linters.bzl)) wraps native `rules_rust`
clippy, kept non-blocking so a violation never breaks `bazel build`:

- `rust_clippy` runs in capture mode (`--@rules_rust//rust/settings:capture_clippy_output`,
  set in [`.bazelrc`](../../.bazelrc)) — the action always succeeds and writes
  clippy's diagnostics to `<crate>.clippy.out`.
- an `sh_test` ([`clippy_assert_empty.sh`](clippy_assert_empty.sh)) fails when that
  file is non-empty, giving the same red/green `lint` test as the other languages.

## Opt-Out

### Per-package — `# gazelle:lint_ignore`

Add the directive at the top of a BUILD to skip the entire package. Useful
for packages whose rules look lintable but aren't (e.g. `java_binary` rules
that wrap prebuilt JARs via `runtime_deps` with no `srcs` of their own —
`tools/lint/BUILD` itself uses this).

```python
# gazelle:lint_ignore

java_binary(
    name = "wrapper",
    runtime_deps = ["@some_external_jar//:lib"],
)
```

On the next `bazel run //:lint_gen`, any pre-existing lint_test rules in this
package are removed and the corresponding load lines are pruned.

### Per-package (frozen) — `# gazelle:lint_ignore_keep`

Like `lint_ignore`, but **preserves** the package's existing lint_test rules
instead of pruning them: `lint_gen` neither generates nor removes lint tests
here. Use it when the lint tests are hand-managed — for example gated behind
`# --- BEGIN/END feature:lint ---` section markers so they drop out of non-lint
scaffolds (`tools/publish/BUILD` uses this for the mint orchestrator). A plain
`lint_ignore` would *delete* those gated blocks on the next repo-wide run.

```python
# gazelle:lint_ignore_keep
```

To refresh frozen tests, temporarily remove the directive, run
`bazel run //:lint_gen`, re-wrap the regenerated rules in their gating markers,
then restore the directive.

### Per-target — `tags = ["no-lint"]`

Add the tag to a single source rule to skip just that rule. The rest of the
package keeps getting lint coverage.

```python
py_library(
    name = "vendored_thirdparty",
    srcs = glob(["vendor/**/*.py"]),
    tags = ["no-lint"],
)

py_library(
    name = "main_lib",
    srcs = glob(["src/**/*.py"]),
    # no tag → ruff_test sibling is generated
)
```

`no-lint` has no runtime effect on the source rule itself; it is observed
only by the Gazelle generator at lint_gen time. Find all uses with
`bazel query 'attr(tags, no-lint, //...)'`.

## Fixing violations

### Python (ruff) and C++ (clang-tidy)

ruff and clang-tidy emit machine-applicable patches via `aspect_rules_lint`.
Build the patches, then apply them:

```bash
# Build patches into bazel-bin (scope to a package, or use //... for the repo)
bazel build \
  --@aspect_rules_lint//lint:fix \
  --output_groups=rules_lint_patch \
  --remote_download_regex='.*AspectRulesLint.*' \
  //...

# Apply every non-empty patch
find bazel-bin -name "*.patch" -size +0 -exec patch -p1 -i {} \;
```

`--remote_download_regex` forces patch outputs local under
`--remote_download_minimal`; `-size +0` skips empty patches (no violations).

### Rust (clippy)

Native `rust_clippy` has no Bazel auto-fix (clippy's `--fix` needs cargo, which
isn't wired into the hermetic build). Run the failing lint test to read each
diagnostic — most carry a suggested fix and a rule URL — then fix by hand:

```bash
bazel test --test_tag_filters=lint //modules/rust_app:rust_app.lint --test_output=errors
```

Style-only issues are formatting, not clippy: run `bazel run //tools/format:format`.

## Architecture

- [`gazelle/`](gazelle/) — the Gazelle language extension (Go). Each
  per-language generator lives in its own `cpp.go` / `rust.go` / `java.go` /
  `python.go` file, wrapped in `// --- BEGIN lang:X ---` markers so a
  scaffolded fork compiles only the languages it selected.
- [`linters.bzl`](linters.bzl) — defines the `aspect_rules_lint` aspects
  (`clang_tidy`, `pmd`, `spotbugs`, `ruff`) and their `*_test` factories, plus
  the native-`rules_rust` `clippy_test` macro. The gazelle extension references
  all of them.
- [`BUILD`](BUILD) — wraps `clang-tidy`, `pmd`, and `spotbugs` as Bazel
  binaries that the aspects invoke, and exports `clippy_assert_empty.sh`.
- [`clippy_assert_empty.sh`](clippy_assert_empty.sh) — the Rust clippy gate's
  check: fails when captured clippy output is non-empty.
