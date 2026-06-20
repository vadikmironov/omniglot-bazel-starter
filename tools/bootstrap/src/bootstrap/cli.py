"""Interactive CLI for the bootstrap tool.

Guides the user through repository name, language selection, target
directory, review, and confirmation before scaffolding a new repo.
"""

import argparse
import difflib
import os
import sys
from pathlib import Path

import questionary

from bootstrap.detect import DetectedRepo, detect_repo
from bootstrap.manifest import BootstrapManifest, compute_prune_set, load_manifest, resolve_files
from bootstrap.scaffolder import (
    buildifier_command,
    feature_finalizer_commands,
    feature_remover_commands,
    prune_paths,
    refresh_lock_files,
    run_buildifier_fix,
    run_feature_finalizers,
    run_feature_removers,
    scaffold_repo,
)


def run(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    source_root = _resolve_source_root()
    manifest_path = source_root / "tools" / "bootstrap" / "bootstrap_manifest.toml"
    manifest = load_manifest(manifest_path)

    # ── Welcome ───────────────────────────────────────────────────────
    print()
    print("  Bazel Monorepo Bootstrap Tool")
    print("  ─────────────────────────────")
    print(f"  Source: {source_root}")
    print()

    # ── Target directory ──────────────────────────────────────────────
    # Asked first so an existing repo can be detected and its settings reused,
    # rather than re-interrogating the user on a re-bootstrap.
    target_dir = questionary.text(
        "Target directory:",
        default=str(source_root.parent.as_posix() + "/"),
    ).ask()
    if not target_dir:
        _abort()
    target_path = Path(target_dir).resolve()

    # ── Detect an existing bootstrapped repo, else ask from scratch ────
    detected = detect_repo(target_path, manifest)
    if detected is not None:
        repo_name, selected_languages, selected_features, module_dir = _reuse_detected(detected, manifest)
    else:
        repo_name, selected_languages, selected_features, module_dir = _ask_fresh(target_path, manifest)

    # ── Prune set ─────────────────────────────────────────────────────
    # When re-bootstrapping with a changed selection, some owner-specific files
    # the old selection shipped are no longer shipped. The scaffolder only
    # writes, so those must be deleted separately (and only if still on disk).
    prune_rel: list[str] = []
    removed_features: set[str] = set()
    if detected is not None:
        prune_rel = sorted(
            rel
            for rel in compute_prune_set(
                manifest,
                detected.languages,
                detected.features,
                selected_languages,
                selected_features,
            )
            if (target_path / rel).exists() or (target_path / rel).is_symlink()
        )
        removed_features = detected.features - selected_features

    # ── Resolve files ─────────────────────────────────────────────────
    resolved = resolve_files(manifest, selected_languages, selected_features)

    # ── Review screen ─────────────────────────────────────────────────
    lang_labels = ", ".join(
        manifest.languages[lang].label for lang in ["python", "cpp", "rust", "java", "go"] if lang in selected_languages
    )

    print()
    print("  ═══════════════════════════════════════════════════")
    print("   REVIEW: Files to be generated")
    print("  ═══════════════════════════════════════════════════")
    print()
    feature_labels = ", ".join(manifest.features[f].label for f in sorted(selected_features)) or "(none)"

    print(f"  Repository : {repo_name}")
    print(f"  Target     : {target_path}")
    print(f"  Code dir   : {module_dir}/")
    print(f"  Languages  : {lang_labels}")
    print(f"  Features   : {feature_labels}")
    print()

    print("  Core files (always included):")
    for f in manifest.core_files:
        print(f"    {f}")
    print()

    for lang in ["python", "cpp", "rust", "java", "go"]:
        if lang not in selected_languages:
            continue
        config = manifest.languages[lang]
        print(f"  {config.label} files:")
        for f in config.files:
            print(f"    {f}")
        for d in config.directories:
            print(f"    {d}/ (directory)")
        print()

    # Language files in shared directories
    has_lang_files = False
    for tag, files in manifest.language_files.items():
        tags = [t.strip() for t in tag.split(",")]
        if any(t in selected_languages for t in tags):
            if not has_lang_files:
                print("  Shared directory files:")
                has_lang_files = True
            for f in files:
                if f not in manifest.excluded_files:
                    print(f"    {f}")
    if has_lang_files:
        print()

    print("  Composite files (section-filtered):")
    for f in resolved.composite:
        print(f"    {f}")
    print()

    print("  Generated docs:")
    print("    README.md (starter overview; intro region preserved on re-bootstrap)")
    print()

    print("  New directories:")
    print(f"    {module_dir}/")
    print()

    if prune_rel:
        print("  Files/dirs to be REMOVED (deselected language/feature):")
        for rel in prune_rel:
            suffix = "/" if (target_path / rel).is_dir() else ""
            print(f"    - {rel}{suffix}")
        print()

    remover_cmds = feature_remover_commands(removed_features)
    if remover_cmds:
        print("  Generated targets to be stripped first (deselected feature):")
        for feat, cmd_str in remover_cmds:
            print(f"    [{feat}] {cmd_str}")
        print()

    total = len(resolved.copy) + len(resolved.composite)
    print(f"  Name substitution: '{manifest.original_name}' -> '{repo_name}'")
    print(f"  Total files: ~{total} (plus directory contents)")
    print()
    print("  ═══════════════════════════════════════════════════")
    print()

    # ── Confirmation ──────────────────────────────────────────────────
    if not questionary.confirm("Proceed with scaffolding?", default=True).ask():
        _abort()

    # ── Feature removers (deselected features) ────────────────────────
    # Run first, while the deselected feature's tooling is still intact, so a
    # generator like lint_gen can strip the rules it scattered into user BUILD
    # files before its own tool dir is pruned below.
    if removed_features:
        print()
        print("  Running feature removers...")
        rem_results = run_feature_removers(
            target_path=target_path,
            module_dir=module_dir,
            removed_features=removed_features,
        )
        rem_failed = [f for f, ok in rem_results.items() if not ok]
        if rem_failed:
            print()
            print(f"  Warning: feature removers failed for: {', '.join(rem_failed)}")

    # ── Prune deselected owners ───────────────────────────────────────
    # Done before scaffolding so all confirmations land up front and so the
    # re-rendered baseline isn't deleted out from under us.
    if prune_rel:
        to_delete = _decide_prune(prune_rel, target_path, review=args.review)
        if to_delete:
            removed = prune_paths(target_path, to_delete)
            print()
            print(f"  Removed {len(removed)} orphaned path(s):")
            for rel in removed:
                print(f"    - {rel}")
        else:
            print()
            print("  Skipped deletion — repo may stay inconsistent with the new selection.")

    # ── Scaffold ──────────────────────────────────────────────────────
    print()
    print("  Scaffolding repository...")
    scaffold_repo(
        source_root=source_root,
        target_path=target_path,
        repo_name=repo_name,
        module_dir=module_dir,
        selected_languages=selected_languages,
        selected_features=selected_features,
        manifest=manifest,
        resolved=resolved,
        confirm=_confirm_overwrite if args.review else None,
    )

    # ── Lock file refresh ─────────────────────────────────────────────
    print()
    if questionary.confirm(
        "Refresh dependency lock files? (recommended, requires network + Bazel)",
        default=True,
    ).ask():
        print()
        print("  Refreshing lock files...")
        results = refresh_lock_files(
            target_path=target_path,
            repo_name=repo_name,
            selected_languages=selected_languages,
        )
        failed = [lang for lang, ok in results.items() if not ok]
        if failed:
            print()
            print(f"  Warning: lock refresh failed for: {', '.join(failed)}")
            print("  You can re-run these manually (see commands below).")

    # ── Feature finalizers ────────────────────────────────────────────
    if selected_features:
        print()
        print("  Running feature finalizers...")
        feat_results = run_feature_finalizers(
            target_path=target_path,
            module_dir=module_dir,
            selected_features=selected_features,
        )
        feat_failed = [f for f, ok in feat_results.items() if not ok]
        if feat_failed:
            print()
            print(f"  Warning: feature finalizers failed for: {', '.join(feat_failed)}")

    # ── Buildifier cleanup ────────────────────────────────────────────
    print()
    print("  Formatting Bazel files...")
    buildifier_ok = run_buildifier_fix(target_path=target_path)

    # ── Summary ───────────────────────────────────────────────────────
    print()
    print("  Done! Your new Bazel repository is ready.")
    print()
    print("  Next steps:")
    print(f"    cd {target_path}")
    print("    bazel build //...")
    print("    bazel test //...")
    for feat, cmd_str in feature_finalizer_commands(selected_features):
        print(f"    {cmd_str}   # [{feat}] (re)generate {feat} targets after adding modules")
        # `bazel test //...` excludes lint by default, so show how to run lint tests.
        if feat == "lint":
            print("    bazel test --test_tag_filters=lint //...   # [lint] run the generated lint tests")
    if not buildifier_ok:
        print(f"    {buildifier_command()}   # one-time formatting cleanup")
    print()


def _ask_fresh(target_path: Path, manifest: BootstrapManifest) -> tuple[str, set[str], set[str], str]:
    """Interactively gather settings for a brand-new repository.

    Returns ``(repo_name, languages, features, module_dir)``. The repo name
    defaults to the target directory's basename.
    """
    repo_name = questionary.text(
        "New repository name:",
        default=target_path.name,
        validate=_validate_repo_name,
    ).ask()
    if not repo_name:
        _abort()

    language_choices = [questionary.Choice(title=cfg.label, value=key) for key, cfg in manifest.languages.items()]
    selected = questionary.checkbox(
        "Select languages to include (use space to toggle, enter to confirm):",
        choices=language_choices,
    ).ask()
    if not selected:
        print("\n  No languages selected.")
        _abort()
    selected_languages = set(selected)

    selected_features: set[str] = set()
    if manifest.features:
        feature_choices = [questionary.Choice(title=cfg.label, value=key) for key, cfg in manifest.features.items()]
        feats = questionary.checkbox(
            "Select optional features (space to toggle, enter to confirm):",
            choices=feature_choices,
        ).ask()
        selected_features = set(feats or [])

    selected_languages = _promote_for_features(manifest, selected_languages, selected_features)

    module_dir = questionary.text(
        "Top-level code directory (holds your modules/services/apps):",
        default=manifest.default_module_dir,
        validate=_validate_module_dir,
    ).ask()
    if not module_dir:
        _abort()

    if (
        target_path.exists()
        and any(target_path.iterdir())
        and not questionary.confirm(
            f"  {target_path} already exists and is not empty. Overwrite?",
            default=False,
        ).ask()
    ):
        _abort()

    return repo_name, selected_languages, selected_features, module_dir


def _reuse_detected(detected: DetectedRepo, manifest: BootstrapManifest) -> tuple[str, set[str], set[str], str]:
    """Confirm re-bootstrapping a detected repo; return the settings to use.

    Returns ``(repo_name, languages, features, module_dir)``. By default the
    detected settings are reused verbatim so the user isn't re-asked what the
    repo already declares. The user may instead opt to **change** the
    language/feature selection — added owners then flow through normal
    scaffolding, while dropped owners are pruned later in :func:`run`.
    """
    lang_labels = ", ".join(
        manifest.languages[lang].label for lang in ["python", "cpp", "rust", "java", "go"] if lang in detected.languages
    )
    feat_labels = ", ".join(manifest.features[f].label for f in sorted(detected.features)) or "(none)"
    print()
    print(f"  Detected an existing bootstrapped repo: {detected.name}")
    print(f"    Languages : {lang_labels}")
    print(f"    Features  : {feat_labels}")
    print(f"    Code dir  : {detected.module_dir}/")
    print("  Re-bootstrap refreshes the starter baseline and preserves your")
    print("  user-managed dependency edits.")
    print()
    if not questionary.confirm("  Re-bootstrap this repo?", default=True).ask():
        _abort()

    if not questionary.confirm(
        "  Change the language/feature selection? (otherwise keep current)",
        default=False,
    ).ask():
        return detected.name, detected.languages, detected.features, detected.module_dir

    # Re-present both checkboxes pre-checked with the detected set, so unchecking
    # an entry removes it and checking a new one adds it.
    language_choices = [
        questionary.Choice(title=cfg.label, value=key, checked=key in detected.languages)
        for key, cfg in manifest.languages.items()
    ]
    selected = questionary.checkbox(
        "Select languages to include (space to toggle, enter to confirm):",
        choices=language_choices,
    ).ask()
    if not selected:
        print("\n  No languages selected.")
        _abort()
    selected_languages = set(selected)

    selected_features: set[str] = set()
    if manifest.features:
        feature_choices = [
            questionary.Choice(title=cfg.label, value=key, checked=key in detected.features)
            for key, cfg in manifest.features.items()
        ]
        feats = questionary.checkbox(
            "Select optional features (space to toggle, enter to confirm):",
            choices=feature_choices,
        ).ask()
        selected_features = set(feats or [])

    selected_languages = _promote_for_features(manifest, selected_languages, selected_features)
    return detected.name, selected_languages, selected_features, detected.module_dir


def _promote_for_features(
    manifest: BootstrapManifest,
    selected_languages: set[str],
    selected_features: set[str],
) -> set[str]:
    """Force-add languages required by *selected_features*, with a note.

    Shared by the fresh and re-bootstrap-override flows so a feature like
    ``lint`` can never ship without the language it needs (e.g. ``go``) — even
    if the user just unchecked that language. Returns the augmented set.
    """
    required: set[str] = set()
    for f in selected_features:
        required.update(manifest.features[f].requires)
    missing = required - selected_languages
    if missing:
        pretty = ", ".join(manifest.languages[k].label for k in sorted(missing) if k in manifest.languages)
        feat_labels = ", ".join(manifest.features[f].label for f in sorted(selected_features))
        print(f"  Note: {pretty} required by selected feature(s) [{feat_labels}] — adding.")
    return selected_languages | missing


def _resolve_source_root() -> Path:
    """Determine the source repository root.

    When run via ``bazel run``, uses BUILD_WORKSPACE_DIRECTORY.
    Otherwise falls back to walking up from this file.
    """
    workspace_dir = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
    if workspace_dir:
        return Path(workspace_dir)
    # Fallback: tools/bootstrap/src/bootstrap/cli.py -> repo root (4 levels up)
    return Path(__file__).resolve().parents[4]


def _validate_repo_name(text: str) -> bool | str:
    if not text:
        return "Repository name cannot be empty"
    if " " in text:
        return "Repository name cannot contain spaces"
    if "/" in text or "\\" in text:
        return "Repository name cannot contain path separators"
    return True


def _validate_module_dir(text: str) -> bool | str:
    if not text:
        return "Directory name cannot be empty"
    if " " in text:
        return "Directory name cannot contain spaces"
    if "/" in text or "\\" in text:
        return "Directory name cannot contain path separators"
    return True


def _abort() -> None:
    print("\n  Cancelled.")
    sys.exit(0)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="bootstrap",
        description="Scaffold (or re-bootstrap) a Bazel polyglot monorepo.",
    )
    parser.add_argument(
        "--review",
        action="store_true",
        help=(
            "When overwriting an existing repo, show a diff and ask before "
            "replacing any file that differs from the starter."
        ),
    )
    return parser.parse_args(argv)


def _confirm_overwrite(dst: Path, existing: str, new_content: str) -> bool:
    """--review hook: show a unified diff and ask whether to apply it."""
    diff = difflib.unified_diff(
        existing.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"{dst.name} (current)",
        tofile=f"{dst.name} (starter)",
    )
    print()
    print("".join(diff), end="")
    print()
    return bool(questionary.confirm(f"  Apply starter changes to {dst.name}?", default=True).ask())


# ── Prune decision (deletion of deselected owners) ────────────────────

_PRUNE_DELETE_ALL = "‹Delete all remaining›"
_PRUNE_CANCEL = "‹Cancel — keep everything›"


def _decide_prune(prune_rel: list[str], target_path: Path, *, review: bool) -> list[str]:
    """Return the subset of *prune_rel* the user agreed to delete.

    Default flow: one bulk confirm (default No — deletion is opt-in). With
    ``--review``: an interactive selector to inspect each path and keep or
    delete it individually, reusing the diff-review idiom from
    :func:`_confirm_overwrite`.
    """
    if not review:
        if questionary.confirm(
            f"  Delete the {len(prune_rel)} orphaned path(s) above?",
            default=False,
        ).ask():
            return list(prune_rel)
        return []
    return _review_prune(prune_rel, target_path)


def _review_prune(prune_rel: list[str], target_path: Path) -> list[str]:
    """Interactive per-path deletion review (the ``--review`` prune selector).

    Loops a selector of the remaining paths plus 'delete all' / 'cancel'
    sentinels. Picking a path shows what deleting it removes — a unified
    deletion diff for a file, a recursive file listing for a directory — then
    asks whether to delete it. Returns the staged set of paths to delete.
    """
    pending = list(prune_rel)
    staged: list[str] = []

    while pending:
        choice = questionary.select(
            "Review deletions — pick a path to inspect, or choose an action:",
            choices=[*pending, _PRUNE_DELETE_ALL, _PRUNE_CANCEL],
        ).ask()
        if choice is None or choice == _PRUNE_CANCEL:
            return []
        if choice == _PRUNE_DELETE_ALL:
            return staged + pending
        print()
        print(_render_deletion(target_path / choice, choice), end="")
        print()
        if questionary.confirm(f"  Delete {choice}?", default=True).ask():
            staged.append(choice)
        pending.remove(choice)

    return staged


def _render_deletion(path: Path, rel: str) -> str:
    """Render what deleting *path* removes.

    A unified diff against an empty target for a file (so every line shows as a
    removal, mirroring :func:`_confirm_overwrite`); a recursive file listing for
    a directory, where a per-line diff of a whole tool dir would just be noise.
    """
    if path.is_dir() and not path.is_symlink():
        files = sorted(str(p.relative_to(path)) for p in path.rglob("*") if p.is_file())
        listing = "\n".join(f"      {rel}/{f}" for f in files) or "      (empty)"
        return f"  Directory {rel}/ contains {len(files)} file(s):\n{listing}\n"
    try:
        existing = path.read_text()
    except (UnicodeDecodeError, OSError):
        return f"  {rel} (binary or unreadable — will be deleted)\n"
    diff = difflib.unified_diff(
        existing.splitlines(keepends=True),
        [],
        fromfile=f"{rel} (current)",
        tofile=f"{rel} (deleted)",
    )
    return "".join(diff)
