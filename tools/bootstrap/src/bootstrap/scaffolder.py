"""Repository scaffolder.

Orchestrates all file operations to generate a new Bazel repository:
direct copies, directory copies, composite section filtering, and
name substitutions.
"""

import os
import shlex
import shutil
import stat
import subprocess
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

from bootstrap.manifest import (
    BootstrapManifest,
    ResolvedFiles,
    effective_excluded_files,
    write_bootstrap_marker,
)
from bootstrap.processor import filter_sections, has_user_region, splice_user_region

_PUBLISH_TOML = ".publish.toml"
_BAZELRC = ".bazelrc"
_SOURCE_MODULE_DIR = "modules"

# The starter README is rendered (not copied) from a section-markered template
# in the bootstrap tool itself, so the source repo's own README is never shipped.
# Its user-managed intro region is preserved across re-bootstrap like any other
# managed file; ``{{code_dir}}`` is replaced with the chosen module directory.
_README_TEMPLATE = "tools/bootstrap/templates/README.md"
_README_OUTPUT = "README.md"
_CODE_DIR_PLACEHOLDER = "{{code_dir}}"

# A --review hook: given (dst, existing_content, new_content), return True to
# overwrite the file or False to keep what's on disk. None means no review —
# existing files are overwritten (managed files still keep their user region).
ConfirmOverwrite = Callable[[Path, str, str], bool]


def scaffold_repo(
    *,
    source_root: Path,
    target_path: Path,
    repo_name: str,
    module_dir: str,
    selected_languages: set[str],
    manifest: BootstrapManifest,
    resolved: ResolvedFiles,
    selected_features: set[str] | None = None,
    confirm: ConfirmOverwrite | None = None,
) -> None:
    """Generate (or re-bootstrap) a Bazel repository at *target_path*.

    *module_dir* is the name of the top-level directory that will hold the
    repo's code (placeholder created empty during scaffolding). Any
    publish-convention reference to the default token in bootstrapped
    config files is rewritten to match.

    *selected_features* drives ``feature:X`` section filtering in composite
    files; defaults to the empty set.

    *confirm*, when provided, gates overwrites of pre-existing files that
    differ from the freshly rendered output (the ``--review`` flow). Without
    it, existing files are overwritten — though managed files always carry
    their ``user-managed`` region forward via splicing, re-bootstrap or not.
    """
    selected_features = selected_features or set()
    target_path.mkdir(parents=True, exist_ok=True)

    # Build lookup of files to skip during directory copies. Feature-conditional
    # excludes (e.g. tools/cpp/toolchains/ when custom_toolchains is off) are
    # folded in here so a gated subdirectory is pruned from its language
    # tool-directory copytree.
    composite_abs = {source_root / f for f in resolved.composite}
    excluded_abs = {source_root / f for f in effective_excluded_files(manifest, selected_features)}
    skip_abs = composite_abs | excluded_abs

    # 1. Direct file copies (core + language + language_files)
    print("  Copying files...")
    for rel in resolved.copy:
        _copy_file(source_root / rel, target_path / rel)

    # 2. Directory copies (language tool directories)
    print("  Copying tool directories...")
    for rel_dir in resolved.directories:
        src_dir = source_root / rel_dir
        dst_dir = target_path / rel_dir
        shutil.copytree(
            src_dir,
            dst_dir,
            ignore=_make_ignore(skip_abs),
            dirs_exist_ok=True,
        )

    # 3. Composite files — filter sections, splice user-managed regions, and
    #    honor --review before overwriting anything already on disk.
    print("  Processing composite files...")
    for rel in resolved.composite:
        src = source_root / rel
        content = src.read_text()
        filtered = filter_sections(content, selected_languages, selected_features, filename=rel)
        if module_dir != _SOURCE_MODULE_DIR:
            if rel == _PUBLISH_TOML:
                filtered = filtered.replace(
                    f'"{_SOURCE_MODULE_DIR}/**"',
                    f'"{module_dir}/**"',
                )
            elif rel == _BAZELRC:
                # gcc_analyzer scopes -fanalyzer to first-party sources by
                # module-dir prefix; track a renamed module dir.
                filtered = filtered.replace(
                    f"--per_file_copt={_SOURCE_MODULE_DIR}/",
                    f"--per_file_copt={module_dir}/",
                )
        dst = target_path / rel
        to_write = _resolve_managed(filtered, dst, confirm=confirm)
        if to_write is None:
            print(f"    kept existing {rel}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(to_write)
        # Preserve executable bit
        if os.access(src, os.X_OK):
            dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)

    # 4. Generated starter README — rendered from the bootstrap template,
    #    section-filtered for the selection, with the user-managed intro carried
    #    forward on re-bootstrap. Done before substitutions so its module-name
    #    tokens are rewritten alongside everything else.
    print("  Rendering README...")
    _render_readme(
        source_root=source_root,
        target_path=target_path,
        module_dir=module_dir,
        selected_languages=selected_languages,
        selected_features=selected_features,
        confirm=confirm,
    )

    # 5. Name substitutions across all text files
    print("  Applying name substitutions...")
    _apply_substitutions(target_path, manifest.original_name, repo_name)

    # 6. Create empty placeholder module directory
    (target_path / module_dir).mkdir(exist_ok=True)

    # 7. Record the selection so a re-bootstrap recovers it exactly. Written
    #    after substitutions (its content carries no original_name to rewrite).
    write_bootstrap_marker(target_path, module_dir, selected_languages, selected_features)

    # 8. Git init
    print("  Initializing git repository...")
    subprocess.run(["git", "init"], cwd=target_path, check=True, capture_output=True)  # noqa: S607


def prune_paths(target_path: Path, rel_paths: Iterable[str]) -> list[str]:
    """Delete the *rel_paths* (relative to *target_path*) that exist on disk.

    The counterpart to :func:`scaffold_repo` for re-bootstrap: when a language
    or feature is deselected, its owner-specific artifacts must be removed (see
    :func:`bootstrap.manifest.compute_prune_set`). Directories are deleted
    recursively, files individually. Non-existent entries are ignored, so a
    parent/child overlap is harmless — paths are sorted so a parent
    (``tools/rust``) is removed before its child (``tools/rust/Cargo.toml``),
    leaving the child a no-op. Returns the sorted list actually removed, for the
    caller to report.
    """
    removed: list[str] = []
    for rel in sorted(rel_paths):
        path = target_path / rel
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
            removed.append(rel)
        elif path.exists() or path.is_symlink():
            path.unlink()
            removed.append(rel)
    return removed


# ── Internal helpers ──────────────────────────────────────────────────


def _copy_file(src: Path, dst: Path) -> None:
    """Copy a single file, creating parent directories as needed."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_symlink():
        link_target = src.readlink()
        if dst.exists() or dst.is_symlink():
            dst.unlink()
        dst.symlink_to(link_target)
    else:
        shutil.copy2(src, dst)


def _make_ignore(skip_abs: set[Path]):
    """Return an ignore callable for shutil.copytree that skips files
    present in *skip_abs* (composite or excluded files)."""

    def _ignore(directory: str, names: list[str]) -> set[str]:
        dir_path = Path(directory)
        return {name for name in names if dir_path / name in skip_abs}

    return _ignore


def _resolve_managed(rendered: str, dst: Path, *, confirm: ConfirmOverwrite | None) -> str | None:
    """Compute the content to write for *dst*, or None to leave it untouched.

    On a fresh target the rendered source is written as-is. When the target
    already exists and both it and the rendered source carry a user-managed
    region, that region is spliced through — so a user's dependency edits
    survive a re-bootstrap while the starter baseline is refreshed. When
    *confirm* is supplied (``--review``) and the result differs from what's on
    disk, the user is asked before the file is overwritten.
    """
    existing = dst.read_text() if dst.exists() else None
    new_content = rendered
    if existing is not None and has_user_region(rendered) and has_user_region(existing):
        new_content = splice_user_region(rendered, existing)
    if (
        confirm is not None
        and existing is not None
        and existing != new_content
        and not confirm(dst, existing, new_content)
    ):
        return None
    return new_content


# ── Generated README ──────────────────────────────────────────────────


def _render_readme(
    *,
    source_root: Path,
    target_path: Path,
    module_dir: str,
    selected_languages: set[str],
    selected_features: set[str],
    confirm: ConfirmOverwrite | None,
) -> None:
    """Render the starter README from the bootstrap template into the repo root.

    The template is section-filtered for the selection (so the Pre-commit,
    Publishing, lint, and per-language lock-refresh sections appear only when
    relevant), has its ``{{code_dir}}`` token replaced with *module_dir*, and is
    written through the same managed-overwrite path as composite files — so the
    user-managed intro survives a re-bootstrap and ``--review`` gates overwrites.
    A missing template is a no-op (the rest of the scaffold is unaffected).
    """
    src = source_root / _README_TEMPLATE
    if not src.is_file():
        return
    rendered = filter_sections(src.read_text(), selected_languages, selected_features, filename=_README_OUTPUT)
    rendered = rendered.replace(_CODE_DIR_PLACEHOLDER, module_dir)
    dst = target_path / _README_OUTPUT
    to_write = _resolve_managed(rendered, dst, confirm=confirm)
    if to_write is None:
        print(f"    kept existing {_README_OUTPUT}")
        return
    dst.write_text(to_write)


# ── Name substitution ─────────────────────────────────────────────────

_TEXT_EXTENSIONS = {
    ".bazel",
    ".bazelrc",
    ".bzl",
    ".cfg",
    ".clang-format",
    ".clang-tidy",
    ".gitignore",
    # Go cross-package imports embed the module path — substitute or strict-deps breaks.
    ".go",
    ".ini",
    ".json",
    ".md",
    ".mod",
    ".py",
    ".rs",
    ".sh",
    ".sum",
    ".template",
    ".toml",
    ".xml",
    ".yaml",
    ".yml",
}

# Files with no extension that should be treated as text
_TEXT_NAMES = {
    "BUILD",
    "WORKSPACE",
    "MODULE.bazel",
    ".bazelignore",
    ".bazeliskrc",
    ".bazelrc",
    ".bazelversion",
    ".clang-format",
    ".clang-tidy",
    ".gitignore",
}


def _is_text_file(path: Path) -> bool:
    """Heuristic: is this file likely to be a text file?"""
    if path.name in _TEXT_NAMES:
        return True
    return path.suffix in _TEXT_EXTENSIONS


# ── Lock file refresh ────────────────────────────────────────────────

# Each entry: (language, description, command_args, env_extras)
# command_args is a list; repo_name placeholder {repo} is substituted at runtime.
_LOCK_REFRESH_COMMANDS: list[tuple[str, str, list[str], dict[str, str]]] = [
    (
        "python",
        "Python pip requirements lock",
        ["bazel", "run", "//tools/python:generate_requirements_lock.update"],
        {},
    ),
    (
        "java",
        "Java Maven dependencies lock",
        ["bazel", "run", "@{repo}_maven_dependencies//:pin"],
        {"REPIN": "1"},
    ),
    (
        "rust",
        "Rust crate universe sync",
        ["bazel", "fetch", "@crates//..."],
        {"CARGO_BAZEL_REPIN": "1"},
    ),
    (
        "go",
        "Go module tidy",
        ["bazel", "run", "@rules_go//go", "--", "mod", "tidy"],
        {},
    ),
]


def _format_cmd(cmd: list[str], env_extras: dict[str, str]) -> str:
    """Render *cmd* with any *env_extras* as a copy-pasteable shell string."""
    parts = [f"{k}={shlex.quote(v)}" for k, v in env_extras.items()]
    parts.extend(shlex.quote(c) for c in cmd)
    return " ".join(parts)


def _run_streaming_command(
    *,
    label: str,
    description: str,
    cmd: list[str],
    env_extras: dict[str, str],
    target_path: Path,
) -> bool:
    """Echo *cmd*, run it with output streamed live, return success bool.

    On failure (non-zero exit or OSError), prints a `Re-run manually:` line
    with the exact command. Does not handle ``KeyboardInterrupt`` — that's
    the caller's responsibility so it can report which step was active.
    """
    cmd_str = _format_cmd(cmd, env_extras)
    run_env = {**os.environ, **env_extras}

    print(f"    [{label}] {description}")
    print(f"    [{label}] $ {cmd_str}", flush=True)
    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            cwd=target_path,
            timeout=600,
            env=run_env,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        print(f"    [{label}] FAILED ({e})")
        print(f"    [{label}] Re-run manually: cd {target_path} && {cmd_str}")
        return False

    if result.returncode == 0:
        print(f"    [{label}] OK")
        return True
    print(f"    [{label}] FAILED (exit {result.returncode})")
    print(f"    [{label}] Re-run manually: cd {target_path} && {cmd_str}")
    return False


def _exit_on_interrupt(noun: str, label: str | None, cmd_str: str, target_path: Path) -> None:
    """Print a friendly summary of where SIGINT landed and exit 130."""
    print()
    if label is not None:
        print(f"  Interrupted during [{label}] {noun}.")
        print(f"  To resume manually: cd {target_path} && {cmd_str}")
    else:
        print(f"  Interrupted before any {noun} started.")
    sys.exit(130)


def _prepare_for_refresh(lang: str, target_path: Path) -> None:
    """Per-language preconditions before the refresh command runs."""
    # rules_rust crate_universe refuses to write a lockfile at a path that
    # doesn't already exist; an empty file is enough to make it populate.
    if lang == "rust":
        cargo_lock = target_path / "tools" / "rust" / "Cargo.lock"
        if not cargo_lock.exists():
            cargo_lock.parent.mkdir(parents=True, exist_ok=True)
            cargo_lock.touch()


def refresh_lock_files(
    *,
    target_path: Path,
    repo_name: str,
    selected_languages: set[str],
) -> dict[str, bool]:
    """Run lock file refresh commands for each selected language.

    Output streams live so the user sees Bazel/pip progress (these can take
    many minutes on a cold cache). Failures are best-effort — reported but
    do not raise. A Ctrl-C is caught, the active step is reported with a
    manual resume command, and the process exits cleanly with code 130.
    """
    results: dict[str, bool] = {}
    current_lang: str | None = None
    current_cmd_str = ""

    try:
        for lang, description, cmd_template, env_extras in _LOCK_REFRESH_COMMANDS:
            if lang not in selected_languages:
                continue
            cmd = [arg.replace("{repo}", repo_name) for arg in cmd_template]
            current_lang = lang
            current_cmd_str = _format_cmd(cmd, env_extras)
            _prepare_for_refresh(lang, target_path)
            results[lang] = _run_streaming_command(
                label=lang,
                description=description,
                cmd=cmd,
                env_extras=env_extras,
                target_path=target_path,
            )
    except KeyboardInterrupt:
        _exit_on_interrupt("lock refresh step", current_lang, current_cmd_str, target_path)

    return results


# ── Feature finalizers ──────────────────────────────────────────────

# Each entry: (feature_key, description, command_args, env_extras).
# These run after lock-file refresh, only when the feature is selected
# and the chosen module_dir is non-empty (i.e., there's actual code for
# the finalizer to act on).
_FEATURE_FINALIZERS: list[tuple[str, str, list[str], dict[str, str]]] = [
    (
        "publish",
        "Generate publish targets via gazelle",
        ["bazel", "run", "//:publish_gen"],
        {},
    ),
    (
        "lint",
        "Generate lint_test targets via gazelle",
        ["bazel", "run", "//:lint_gen"],
        {},
    ),
    (
        "profiling",
        "Generate profiling workload targets via gazelle",
        ["bazel", "run", "//:profile_gen"],
        {},
    ),
]


def run_feature_finalizers(
    *,
    target_path: Path,
    module_dir: str,
    selected_features: set[str],
) -> dict[str, bool]:
    """Run per-feature finalizer commands after lock-file refresh.

    Skipped entirely when *module_dir* is empty — finalizers like
    ``publish_gen`` only emit useful output when there's source code to
    scan, and we'd rather not waste 30-60s of a cold gazelle compile on
    a no-op pass. Same streaming/Ctrl-C semantics as
    :func:`refresh_lock_files`.
    """
    if not selected_features:
        return {}

    module_path = target_path / module_dir
    if not module_path.exists() or not any(module_path.iterdir()):
        print(f"  Skipping feature finalizers — {module_dir}/ is empty.")
        print("  Run them once you have code; see 'Next steps' below.")
        return {}

    results: dict[str, bool] = {}
    current_feat: str | None = None
    current_cmd_str = ""

    try:
        for feat, description, cmd_template, env_extras in _FEATURE_FINALIZERS:
            if feat not in selected_features:
                continue
            cmd = list(cmd_template)
            current_feat = feat
            current_cmd_str = _format_cmd(cmd, env_extras)
            results[feat] = _run_streaming_command(
                label=feat,
                description=description,
                cmd=cmd,
                env_extras=env_extras,
                target_path=target_path,
            )
    except KeyboardInterrupt:
        _exit_on_interrupt("feature finalizer", current_feat, current_cmd_str, target_path)

    return results


def feature_finalizer_commands(selected_features: set[str]) -> list[tuple[str, str]]:
    """Return (feature, formatted_command) pairs for the printed `Next steps`
    block, so the user knows how to run finalizers manually."""
    return [
        (feat, _format_cmd(list(cmd), env_extras))
        for feat, _desc, cmd, env_extras in _FEATURE_FINALIZERS
        if feat in selected_features
    ]


# ── Feature removers (re-bootstrap teardown) ─────────────────────────

# Each entry: (feature_key, description, command_args, env_extras).
# These run when a feature is DESELECTED on re-bootstrap, before its tool
# directories are pruned, to undo generation a finalizer had scattered into
# the user's own BUILD files. lint_gen's -lint_remove reaps every generated
# lint_test rule repo-wide; without it those rules would dangle once
# tools/lint/ (and its linters.bzl load target) is deleted.
_FEATURE_REMOVERS: list[tuple[str, str, list[str], dict[str, str]]] = [
    (
        "lint",
        "Strip generated lint_test targets",
        ["bazel", "run", "//:lint_gen", "--", "-lint_remove"],
        {},
    ),
    (
        "publish",
        "Strip generated publish targets",
        ["bazel", "run", "//:publish_gen", "--", "-publish_remove"],
        {},
    ),
    (
        "profiling",
        "Strip generated profiling workload targets",
        ["bazel", "run", "//:profile_gen", "--", "-profiling_remove"],
        {},
    ),
]


def run_feature_removers(
    *,
    target_path: Path,
    module_dir: str,
    removed_features: set[str],
) -> dict[str, bool]:
    """Run per-feature teardown for features deselected on re-bootstrap.

    The drop-side mirror of :func:`run_feature_finalizers`: a generator like
    ``lint_gen`` strips the rules it had emitted into user BUILD files. Must run
    *before* the feature's tool directories are pruned (the generator binary
    lives in them) and before scaffolding re-renders ``MODULE.bazel`` — i.e. on
    the still-intact target. Skipped when *module_dir* is empty (no user code ⇒
    nothing was generated to strip). Same streaming / Ctrl-C semantics as
    :func:`run_feature_finalizers`.
    """
    if not removed_features:
        return {}

    module_path = target_path / module_dir
    if not module_path.exists() or not any(module_path.iterdir()):
        print(f"  Skipping feature removers — {module_dir}/ is empty.")
        return {}

    results: dict[str, bool] = {}
    current_feat: str | None = None
    current_cmd_str = ""

    try:
        for feat, description, cmd_template, env_extras in _FEATURE_REMOVERS:
            if feat not in removed_features:
                continue
            cmd = list(cmd_template)
            current_feat = feat
            current_cmd_str = _format_cmd(cmd, env_extras)
            results[feat] = _run_streaming_command(
                label=feat,
                description=description,
                cmd=cmd,
                env_extras=env_extras,
                target_path=target_path,
            )
    except KeyboardInterrupt:
        _exit_on_interrupt("feature remover", current_feat, current_cmd_str, target_path)

    return results


def feature_remover_commands(removed_features: set[str]) -> list[tuple[str, str]]:
    """Return (feature, formatted_command) pairs for the removers that apply to
    *removed_features*, so the review screen can tell the user which generated
    targets will be stripped before pruning."""
    return [
        (feat, _format_cmd(list(cmd), env_extras))
        for feat, _desc, cmd, env_extras in _FEATURE_REMOVERS
        if feat in removed_features
    ]


# Run last so it cleans up any BUILD output that publish_gen / lint_gen
# may have emitted, plus the cosmetic blank lines left behind by section-
# marker stripping in MODULE.bazel / linters.bzl / etc.
_BUILDIFIER_CMD: list[str] = ["bazel", "run", "//:buildifier.fix"]


def run_buildifier_fix(*, target_path: Path) -> bool:
    """Run buildifier.fix on the scaffolded repo. Best-effort, non-fatal."""
    cmd_str = _format_cmd(_BUILDIFIER_CMD, {})
    try:
        return _run_streaming_command(
            label="buildifier",
            description="Format Bazel files",
            cmd=list(_BUILDIFIER_CMD),
            env_extras={},
            target_path=target_path,
        )
    except KeyboardInterrupt:
        _exit_on_interrupt("buildifier", "buildifier", cmd_str, target_path)
        return False  # unreachable


def buildifier_command() -> str:
    """Return the formatted buildifier command for the `Next steps` block."""
    return _format_cmd(list(_BUILDIFIER_CMD), {})


def _apply_substitutions(target_path: Path, original_name: str, new_name: str) -> None:
    """Replace original_name with new_name in all text files under target_path."""
    for path in target_path.rglob("*"):
        if path.is_file() and _is_text_file(path):
            try:
                content = path.read_text()
            except (UnicodeDecodeError, PermissionError):
                continue
            if original_name in content:
                path.write_text(content.replace(original_name, new_name))
