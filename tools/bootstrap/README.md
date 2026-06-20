# Bootstrap

Scaffold a brand-new Bazel polyglot monorepo from this starter, shipping only the languages and features you choose. Re-run it on a repo it already scaffolded to refresh the baseline or change the selection.

## Usage

Run from the root of this repository:

```bash
# Interactive — prompts for every choice
bazel run //tools/bootstrap

# Review mode — show a diff and confirm before overwriting any file that
# differs from the starter, and inspect each path before it is pruned on
# a re-bootstrap
bazel run //tools/bootstrap -- --review
```

## What it asks

1. **Target directory** — where the new repo is created (defaults next to this one).
2. **Repository name** — substituted for `omniglot-bazel-starter` throughout (module name, labels, repo names).
3. **Languages** — any subset of Python, Rust, C++, Java, Go.
4. **Optional features:**
   - `lint` — the full static-analysis pipeline (the `rules_lint` aspects, mypy, bandit, Go `nogo`) plus the `lint_gen` rule generator.
   - `publish` — the `publish_gen` Gazelle extension that emits `:publish` targets for Maven / PyPI / generic registries.
   - `custom_toolchains` — the non-default host/local toolchains for each selected language (host GCC/Clang, host Python, local Go SDK, and all Corretto JDKs). These are machine-specific, so they're opt-in; the hermetic defaults always ship. No-op for Rust.

   A feature auto-adds any language it requires.
5. **Code directory** — the top-level dir that holds your modules/services/apps (default `modules`).

## What it does

After you confirm the review screen, it:

1. Copies a **filtered** subset of this repo — only the files and tool dirs for the selected languages and features — into the target directory.
2. Generates a starter `README.md` — initial Bazelisk install, common repo commands, and other useful information on developer's setup. Its intro is a user-managed region you can edit; a re-bootstrap refreshes the rest but keeps your intro.
3. Rewrites the module name everywhere and `git init`s the result.
4. Optionally refreshes dependency lock files for the selected languages (needs network + Bazel).
5. Runs per-feature finalizers (`lint_gen`, `publish_gen`) and formats the generated Bazel files.

It finishes by printing your next steps (`cd …`, `bazel build //...`, `bazel test //...`).

## Re-bootstrapping

Point the tool at a directory it previously scaffolded and it detects the earlier selection from the `.omniglot_bootstrap.toml` marker it writes there. From a detected repo you can:

- **Refresh** the starter baseline in place — edits you made inside `BEGIN/END user-managed` regions are carried forward, or
- **Change** the selection — checking a language/feature adds it, unchecking removes it. Files owned solely by a removed language/feature are pruned after an explicit confirmation (or, with `--review`, a per-path selector). A removed `lint` or `publish` feature also has its generated rules torn down across your BUILD files first.

## Internals

The manifest format, the section-marker filtering engine, and how to add a language or feature are documented in [AGENTS.md](AGENTS.md).
