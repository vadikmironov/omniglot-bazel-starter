# Bootstrap module — agent guide

Scaffolds (or re-bootstraps) a new Bazel polyglot monorepo from this starter,
shipping only the languages and optional features the user selects.

## Entry point & flow

`bazel run //tools/bootstrap` → `src/bootstrap/cli.py`. It asks for target dir,
repo name, languages, optional features, and code dir; then copies a *filtered*
subset of this repo into the target, rewrites the module name, `git init`s, and
(optionally) refreshes lock files and runs per-feature finalizers.

## Files

- `bootstrap_manifest.toml` — single source of truth for what ships where.
- `src/bootstrap/manifest.py` — loads the manifest; `resolve_files()` computes the
  file set for a selection; `effective_excluded_files()` applies feature-conditional excludes.
- `src/bootstrap/processor.py` — the section-marker filter (`filter_sections`) and
  user-managed region splicing (`splice_user_region`).
- `src/bootstrap/scaffolder.py` — orchestrates copy → filter → render-README →
  substitute → git, then lock-file refresh and `_FEATURE_FINALIZERS` (e.g.
  `publish_gen`, `lint_gen`). `_render_readme` filters `templates/README.md` for the
  selection, swaps the `{{code_dir}}` token, and writes `README.md` through the same
  managed-overwrite path as composite files (user-managed intro preserved on re-bootstrap).
- `templates/README.md` — section-markered template for the *generated* repo README.
  It is rendered, not shipped, so the source repo's own `README.md` never reaches a
  scaffolded repo. Carries `#`-style `lang:`/`feature:` markers (stripped at render)
  plus an HTML-comment `user-managed` intro region (survives into the output).
- `src/bootstrap/detect.py` — re-bootstrap detection. *Authoritative, not heuristic*: name
  from `MODULE.bazel`, everything else from the `.omniglot_bootstrap.toml` marker
  (`manifest.read_bootstrap_marker`). No marker ⇒ `None` (treated as a fresh repo, user is
  asked) — there is deliberately no filesystem-guessing fallback.
- `tests/` — run with `PYTHONPATH=src python3 tests/<file>.py` (pure Python, no Bazel needed).

## Re-bootstrap override (changing the selection)

Every scaffold writes a `.omniglot_bootstrap.toml` marker (`[repo]` →
`module_dir`, `languages`, `features`) via `manifest.write_bootstrap_marker`,
rewritten on each re-bootstrap. `detect.detect_repo` reads it back exactly, so
re-bootstrap never guesses the code dir or selection from the filesystem.

On a detected repo, `_reuse_detected` reuses the detected languages/features by
default, but offers to **change** them: it re-presents both checkboxes
pre-checked with the detected set (uncheck = remove, check = add), then
re-promotes any language a selected feature `requires` (`_promote_for_features`,
shared with `_ask_fresh` — no auto-demotion; the checkbox is the truth).

*Adds* just flow through normal resolution + scaffolding. *Removals* need
deletion (the scaffolder only writes): `manifest.compute_prune_set(old_langs,
old_feats, new_langs, new_feats)` returns the orphaned paths — the
`copy ∪ directories ∪ composite` diff (owner-exclusive files/dirs/composite;
*always-shipped* composite like `MODULE.bazel` stays in both sets and is merely
re-rendered) **plus** the `effective_excluded_files` delta (for
`when_feature_absent` configs like `tools/cpp/toolchains` that hide inside a
surviving language dir). `run` filters that to on-disk paths and, after an
explicit confirm (or per-path `--review` selector), deletes them via
`scaffolder.prune_paths` before scaffolding. Composite files that *survive*
self-heal — deselected `feature:`/`lang:` sections vanish on re-render.

A *deselected* feature whose finalizer scattered rules into the user's own
BUILD files needs teardown those diffs can't reach: `run_feature_removers`
(the `_FEATURE_REMOVERS` table) runs **before** the prune, on the still-intact
target. `lint` → `bazel run //:lint_gen -- -lint_remove` reaps every generated
`lint_test` rule before `tools/lint/` (its `linters.bzl` load target) is
deleted; `publish` → `bazel run //:publish_gen -- -publish_remove` reaps every
`:publish` / `:publish_image` rule before `tools/publish/` is deleted. Both
extensions gate the reap behind a `removeAll` flag (`lang.go`) wired to a
`computeEmpty` over the kinds they own. The *add* side needs nothing new — the
existing `_FEATURE_FINALIZERS` already runs `lint_gen` / `publish_gen` whenever
the feature is selected.

## Manifest sections

- `[core]` — files/dirs always shipped. `directories` includes `tools/setup` (the
  Bazelisk installer) — every repo needs Bazel regardless of language/feature choice.
- `[languages.X]` — per-language root files + tool dirs (shipped iff X selected).
- `[features.X]` — opt-in capabilities. May declare `requires` (languages auto-promoted),
  `directories`, `files`, `composite_files`, and `[features.X.composite_language_files]`
  (per-language composite files gated on feature **AND** language — e.g. lint's per-language
  gazelle generators). Current: `publish`, `lint` (both require `go`), `coverage`,
  `profiling` (requires `rust`+`go`+`python`), `custom_toolchains` and `remote_cache`
  (the last two take no `requires` and own no files — they gate via markers/excludes
  only; see below).
- `[language_files]` — individual files in shared dirs, keyed by comma-tag (OR over languages).
- `[composite]` — files always run through the section filter (always shipped).
- `[composite_language_files]` — composite files shipped only when their language is
  selected. Keys may be comma OR-tags: `.clang-format` is keyed `cpp,java` (clang-format
  formats only those), and `.pre-commit-config.yaml` rides with `python` (the pre-commit
  binary is installed from the Python `.venv`). A composite file here with a `lang:core`
  section therefore won't leak that section into selections that exclude its owner.
- `[exclude]` — files never shipped. `[exclude.when_feature_absent].FEAT` drops files when
  FEAT is not selected, layered on top of language ownership (→ "language AND feature").
- `[substitutions]` — rewrites `original_name` to the repo name in every text file.

## Section-marker engine (`processor.filter_sections`)

Composite files carry markers that are consumed (stripped) at scaffold time:

```
# --- BEGIN lang:python ---        (// also accepted, e.g. go.mod / JSON-ish)
...
# --- END lang:python ---
```

Tag grammar — two operators, distinct precedence:

- comma = **OR** within a predicate: `lang:cpp,java`
- space = **AND** between predicates: `feature:lint lang:python`

So `lang:cpp,java feature:lint` means "(cpp OR java) AND lint". Predicates are
`lang:core` (always in), `lang:<x>`, `feature:<x>`, or `exclude` (always out).

Rules: sections must **not nest** — a multi-condition tag expresses what nesting
otherwise would; the END marker must repeat the BEGIN tag; a stray/mismatched/unclosed
marker raises `ValueError`.

`# --- BEGIN/END user-managed ---` regions are *not* filtered — they survive into the
output and their body is carried forward on re-bootstrap, so user edits persist. The
marker also accepts `//` and a Markdown HTML-comment form
(`<!-- --- BEGIN user-managed --- -->`) so the generated README can host one without
rendering it as a heading.

The root `BUILD` carries one such region (just after `package(...)`) wrapping a
`_BUILDIFIER_EXCLUDES` constant that the buildifier targets consume. Scaffolded
repos drop their repo-specific Gazelle directives (`# gazelle:exclude <dir>`) and
buildifier exclude tweaks there so they survive re-bootstrap while the rule
definitions stay template-managed.

## Language vs. feature gating (mental model)

- **Formatters** (ruff-format, clang-format, rustfmt, gofumpt) come from toolchains /
  Bazel binaries — always on per language, no external deps.
- The **`lint` feature** owns *all* static analysis: the rules_lint aspects
  (ruff / ty / clang-tidy / clippy / pmd / spotbugs), bandit, Go `nogo`,
  and the gazelle `lint_gen` autogen. Lint OFF ⇒ none of those and none of their deps
  (no pmd/spotbugs Maven, no ruff/bandit/ty pip, no nogo registration).
  The gazelle extension itself ships as **composite files**, not a verbatim `directories`
  copy: `gazelle/{lang.go,BUILD,kinds.go,generate.go}` are section-filtered to the selection
  and the single-language `gazelle/{cpp,rust,java,python}.go` generators ride in
  `[features.lint.composite_language_files]` so an omitted language's generator is absent.
  (A `directories` copy would have leaked every `lang:` marker and shipped all generators.)
  The shared `tools/gazelle/{directives,vocab}` vocabulary is depended on by *every*
  generator's gazelle_binary (lint_gen **and** publish_gen), so it ships when lint **OR**
  publish is selected — enumerated identically under both features' `composite_files`
  (resolve_files de-dupes the overlap), and pruned only once both are dropped. `directives.go`
  is marker-gated per feature, hence composite rather than a raw copy.
- The **`remote_cache` feature** owns the BuildBuddy remote-cache wiring: the
  `build:remote-cache` / `build:ci` configs in `.bazelrc`, the API-key block in
  `user.bazelrc.template`, and the README "Remote Cache" section — all wrapped in
  `feature:remote_cache` markers. It owns no files and has no `requires` (caching is
  language-agnostic). The `try-import user.bazelrc` line stays `lang:core` (the template
  still ships its shared-repo-cache / publish blocks regardless).
- The **`custom_toolchains` feature** owns each language's *non-default* (host / local /
  custom-remote) toolchain wiring beyond the hermetic default — gcc/clang host (C++),
  host interpreter (Python), local SDK (Go), and **all** Corretto incl. remote (Java).
  It owns no files: the `.bazelrc` configs and MODULE-segment registrations are wrapped in
  `feature:custom_toolchains` (segments) / `feature:custom_toolchains lang:X` (`.bazelrc`)
  markers, and the whole `tools/<lang>/toolchains` dirs ride via
  `[exclude.when_feature_absent].custom_toolchains`. `cpp_segment.MODULE.bazel` is a
  composite_language_file so its host register block can be filtered (the `rules_cc` dep
  stays). No `requires` and a no-op for Rust (rules_rust has no local toolchain). The
  hermetic defaults (LLVM, rules_python download, `remotejdk_17`, remote Go SDK) always stay.
- A composite file ships only when its language is selected; a `feature:` section inside
  it adds the feature condition. For **always-shipped** files (`.bazelrc`, root `BUILD`)
  that need *both*, use a multi-condition tag (`feature:lint lang:python`). For whole,
  marker-less config files (`.nogo_config.json`, `.pmd.xml`,
  `.spotbugs-exclude.xml`) use `[exclude.when_feature_absent].lint`.
- `.clang-tidy` / `.clippy.toml` / `ty.toml` are intentionally left ungated (their tools
  come from the toolchain / rules_lint — no dep to gate). `.ruff.toml` ships for the formatter; only
  its `[lint]` block is gated.

## Gazelle-generated lint rules (important)

`lint_test` rules (`ruff_test`, `pmd_test`, …) in BUILD files are emitted by
`bazel run //:lint_gen` (`tools/lint/gazelle`). Comment markers around them are **not**
durable — gazelle rewrites the rules and ignores the comments. To hand-gate such rules
in a shipped file (e.g. `tools/publish/BUILD`), mark the package
`# gazelle:lint_ignore_keep` (freeze: lint_gen neither generates nor prunes there), then
keep the rules wrapped in `feature:lint` markers. Plain `# gazelle:lint_ignore` *prunes*
(deletes) lint rules instead. To regenerate frozen rules: remove the directive, run
lint_gen, re-wrap the emitted rules in `feature:lint`, restore the directive.

The extension also takes a global `-lint_remove` flag (`lang.go` → `removeAll`): it
suppresses generation in every package so `computeEmpty` reaps **all** `lint_test` rules
repo-wide (frozen `lint_ignore_keep` packages excepted). This is the whole-feature
teardown the bootstrap tool runs when `lint` is dropped on re-bootstrap.

## Extending

- **New language**: add `[languages.X]`; add its MODULE.bazel segment + tool dir wrapped
  in `lang:X` markers; add a `[composite_language_files]` entry; add a gazelle generator
  `tools/lint/gazelle/X.go` and register it under `[features.lint.composite_language_files].X`
  (so it ships only with lint **and** that language), plus its `lang:X` block in
  `gazelle/{BUILD,kinds.go,generate.go}`. The 31-subset scaffolder tests cover it automatically.
- **New feature**: add `[features.X]` (+ `requires`); wrap its content in `feature:X`
  markers across composite files; optionally add a `_FEATURE_FINALIZERS` entry.
- **Gate a lint-only config file**: add it to `[exclude.when_feature_absent].lint`.

## Verify

`for t in tests/*.py; do PYTHONPATH=src python3 "$t"; done`. After editing Bazel files,
also run `bazel run //:buildifier.fix` and a real `bazel run //tools/bootstrap` smoke
test (scaffold a repo and confirm it builds). The gazelle extension is Go — changes to
`tools/lint/gazelle/*.go` need a `bazel run //:lint_gen` to compile/verify.
