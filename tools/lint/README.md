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

### C++ clang-tidy

Each `lint_test` reads the exit code of its linter. clang-tidy exits 0 when it
finds only warnings, so [`.clang-tidy`](../../.clang-tidy) sets
`WarningsAsErrors: '*'`. With this setting, each enabled check fails the test.
Generated headers under `bazel-out/` are not linted: [`linters.bzl`](linters.bzl)
passes `--exclude-header-filter` for them. Examples are the headers that a
`rules_foreign_cc` install writes and the interpreter-path header from
`rules_python`. The first-party headers of a target stay linted through
`lint_target_headers`.

Put project-specific check globs in the `user-managed` region at the end of
the `Checks` list. Globs apply in order and the last match wins, so an entry
there can disable a check or enable one again. The bootstrap tool keeps that
region when it re-bootstraps the repo.

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
Apply the lint aspects with the fix flag, build the patch output group, then
apply the patches:

```bash
# Build patches into bazel-bin (scope to a package, or use //... for the repo).
# Name the aspects of the languages in the repo: %ruff (Python), %clang_tidy (C++).
bazel build \
  --aspects=//tools/lint:linters.bzl%ruff,//tools/lint:linters.bzl%clang_tidy \
  --@aspect_rules_lint//lint:fix \
  --output_groups=rules_lint_patch \
  --remote_download_regex='.*AspectRulesLint.*' \
  //...

# Apply every non-empty patch. bazel-bin is a symlink: find needs -L.
find -L bazel-bin -name "*.patch" -size +0 -exec patch -p1 -N -i {} \;

# clang-tidy fix-its do not indent the braces they add. Format the changed files.
bazel run //tools/format:format -- $(git diff --name-only)
```

Without `--aspects` the build has no lint actions and writes no patches; the
`.lint` test targets do not expose the patch output group, so `//...` alone is
not enough. `--remote_download_regex` forces patch outputs local under
`--remote_download_minimal`; `-size +0` skips empty patches (no violations);
`-N` skips hunks that an earlier patch already applied.

#### C++ headers

A patch covers only the `srcs` of its target. Fix-its in headers are never
written to a patch, so the command above leaves every header, and every
header-only library, unchanged. Fix headers with a direct `clang-tidy --fix`
run from the execution root, with the compile flags of the lint action of a
target that includes them:

```bash
# 1. Run the lint test of a target that includes the headers, so the clang-tidy
#    binary and the action's inputs exist. Then read the binary path and the
#    compile flags (everything after `--`) from that lint action.
bazel test --test_tag_filters=lint //modules/cpp_library:cpp_library.lint
ACTION=$(bazel aquery --aspects=//tools/lint:linters.bzl%clang_tidy \
  'mnemonic("AspectRulesLintClangTidy", //modules/cpp_library:cpp_library)')
CLANG_TIDY=$(grep -oE '[^ ]*tools/lint/clang_tidy' <<< "$ACTION" | head -1)
awk '/Command Line:/ {c = 1} c && /^ +-- \\$/ {a = 1; next}
     c && a {sub(/^ +/, ""); sub(/ \\$/, ""); if (sub(/\)$/, "")) {print; exit}; print}' <<< "$ACTION" \
  | sed -E "s/^'(.*)'$/\1/" > /tmp/tidy-flags

# 2. Run clang-tidy --fix from the execution root. Source directories are
#    symlinks there, so the fixes land in the working tree.
cd "$(bazel info execution_root)"
FLAGS=(); while IFS= read -r f; do FLAGS+=("$f"); done < /tmp/tidy-flags
"$CLANG_TIDY" --fix --config-file=.clang-tidy \
  '--header-filter=modules/cpp_library/include/.*' \
  modules/cpp_library/src/cpp_library.cpp -- "${FLAGS[@]}"
```

Use the flags of the lint action unchanged. With other flags the translation
unit can fail to compile, and clang-tidy then applies no fixes. Fix-its that
overlap are skipped; run the command a second time to apply them. Review the
result with `git diff`, then format the headers as above.

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
