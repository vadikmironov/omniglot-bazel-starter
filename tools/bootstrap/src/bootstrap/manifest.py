"""Bootstrap manifest loader.

Parses bootstrap_manifest.toml and resolves the set of files to include
in a new repository based on the user's language selection.
"""

import hashlib
import json
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import tomllib

# Marker file written into every scaffolded repo, recording the selection and
# the file inventory so a re-bootstrap recovers them exactly instead of
# inferring them from the filesystem.
BOOTSTRAP_MARKER_FILE = ".omniglot_bootstrap.toml"


@dataclass
class LanguageConfig:
    label: str
    files: list[str] = field(default_factory=list)
    directories: list[str] = field(default_factory=list)


@dataclass
class FeatureConfig:
    """Optional cross-cutting capability the user can toggle on top of languages."""

    label: str
    requires: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    directories: list[str] = field(default_factory=list)
    composite_files: list[str] = field(default_factory=list)
    # Plain (marker-free) per-language files owned by this feature, keyed by
    # comma-tag (OR over languages). The raw-copy analog of
    # composite_language_files; shipped when the feature AND a language match.
    language_files: dict[str, list[str]] = field(default_factory=dict)
    # Per-language composite files owned by this feature, keyed by comma-tag
    # (OR over languages). Shipped only when the feature AND a matching language
    # are both selected — e.g. the lint feature's per-language gazelle generators.
    composite_language_files: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class BootstrapManifest:
    default_module_dir: str
    languages: dict[str, LanguageConfig]
    features: dict[str, FeatureConfig]
    core_files: list[str]
    core_directories: list[str]
    language_files: dict[str, list[str]]
    composite_files: list[str]
    composite_language_files: dict[str, list[str]]
    excluded_files: list[str]
    excluded_when_feature_absent: dict[str, list[str]]
    original_name: str


@dataclass
class ResolvedFiles:
    """The resolved set of files for a given language selection."""

    copy: list[str] = field(default_factory=list)
    directories: list[str] = field(default_factory=list)
    composite: list[str] = field(default_factory=list)


def load_manifest(manifest_path: Path) -> BootstrapManifest:
    """Load and parse the bootstrap manifest TOML file."""
    with manifest_path.open("rb") as f:
        data = tomllib.load(f)

    languages = {}
    for key, value in data.get("languages", {}).items():
        languages[key] = LanguageConfig(
            label=value["label"],
            files=value.get("files", []),
            directories=value.get("directories", []),
        )

    features = {}
    for key, value in data.get("features", {}).items():
        features[key] = FeatureConfig(
            label=value["label"],
            requires=value.get("requires", []),
            files=value.get("files", []),
            directories=value.get("directories", []),
            composite_files=value.get("composite_files", []),
            language_files=value.get("language_files", {}),
            composite_language_files=value.get("composite_language_files", {}),
        )

    return BootstrapManifest(
        default_module_dir=data["repo"]["default_module_dir"],
        languages=languages,
        features=features,
        core_files=data["core"]["files"],
        core_directories=data["core"].get("directories", []),
        language_files=data.get("language_files", {}),
        composite_files=data["composite"]["files"],
        composite_language_files=data.get("composite_language_files", {}),
        excluded_files=data.get("exclude", {}).get("files", []),
        excluded_when_feature_absent=data.get("exclude", {}).get("when_feature_absent", {}),
        original_name=data["substitutions"]["original_name"],
    )


def effective_excluded_files(
    manifest: BootstrapManifest,
    selected_features: set[str],
) -> set[str]:
    """Return the files/dirs to skip for the given *selected_features*.

    Combines the unconditional ``[exclude] files`` with any
    ``[exclude.when_feature_absent]`` group whose feature is not selected. This
    layers a feature condition on top of a file's existing language ownership:
    e.g. ``.pmd.xml`` (a Java file) is dropped unless ``lint`` is selected,
    so it ships only when Java *and* lint are both on.
    """
    excluded = set(manifest.excluded_files)
    for feature, files in manifest.excluded_when_feature_absent.items():
        if feature not in selected_features:
            excluded.update(files)
    return excluded


def all_composite_files(manifest: BootstrapManifest) -> set[str]:
    """Return every file named in any composite list, selected or not.

    These files carry section markers, so a language tool-directory copy
    must never ship them raw: a selected one is written marker-filtered by
    the composite pass, an unselected one (e.g. a per-language generator
    whose language is off) must not land in the scaffold at all.
    """
    files: set[str] = set(manifest.composite_files)
    for group in manifest.composite_language_files.values():
        files.update(group)
    for feat in manifest.features.values():
        files.update(feat.composite_files)
        for group in feat.composite_language_files.values():
            files.update(group)
    return files


def effective_languages(
    manifest: BootstrapManifest,
    selected_languages: set[str],
    selected_features: set[str],
) -> set[str]:
    """Return *selected_languages* augmented with languages required by *selected_features*."""
    effective = set(selected_languages)
    for feat_key in selected_features:
        feat = manifest.features.get(feat_key)
        if feat is not None:
            effective.update(feat.requires)
    return effective


def resolve_files(
    manifest: BootstrapManifest,
    selected_languages: set[str],
    selected_features: set[str] | None = None,
) -> ResolvedFiles:
    """Resolve which files to include based on selected languages and features.

    Languages required by selected features are folded into the effective set,
    so callers do not have to pre-promote them.
    """
    selected_features = selected_features or set()
    selected_languages = effective_languages(manifest, selected_languages, selected_features)

    excluded = effective_excluded_files(manifest, selected_features)
    resolved = ResolvedFiles()

    # Core files — always included
    for f in manifest.core_files:
        if f not in excluded:
            resolved.copy.append(f)

    # Core directories — always included
    resolved.directories.extend(manifest.core_directories)

    # Language-specific files and directories
    for lang in selected_languages:
        if lang in manifest.languages:
            config = manifest.languages[lang]
            for f in config.files:
                if f not in excluded:
                    resolved.copy.append(f)
            resolved.directories.extend(config.directories)

    # Language files in shared directories (OR logic on comma-separated tags)
    for tag, files in manifest.language_files.items():
        tags = [t.strip() for t in tag.split(",")]
        if any(t in selected_languages for t in tags):
            for f in files:
                if f not in excluded:
                    resolved.copy.append(f)

    # Composite files — always processed (section filter handles language selection)
    resolved.composite = [f for f in manifest.composite_files if f not in excluded]

    # Language-specific composite files (OR logic on comma-separated tags)
    for tag, files in manifest.composite_language_files.items():
        tags = [t.strip() for t in tag.split(",")]
        if any(t in selected_languages for t in tags):
            for f in files:
                if f not in excluded:
                    resolved.composite.append(f)

    # Feature files / directories / composite files
    for feat_key in selected_features:
        feat = manifest.features.get(feat_key)
        if feat is None:
            continue
        for f in feat.files:
            if f not in excluded:
                resolved.copy.append(f)
        resolved.directories.extend(feat.directories)
        # Per-language raw-copy files (feature AND language): feature gate is this
        # loop's membership; language gate is the OR-tag match.
        for tag, files in feat.language_files.items():
            tags = [t.strip() for t in tag.split(",")]
            if any(t in selected_languages for t in tags):
                for f in files:
                    if f not in excluded:
                        resolved.copy.append(f)
        for f in feat.composite_files:
            if f not in excluded:
                resolved.composite.append(f)
        # Per-language composite files (feature AND language): the feature gate is
        # this loop's membership; the language gate is the OR-tag match below.
        for tag, files in feat.composite_language_files.items():
            tags = [t.strip() for t in tag.split(",")]
            if any(t in selected_languages for t in tags):
                for f in files:
                    if f not in excluded:
                        resolved.composite.append(f)

    # A file shared by two features (e.g. tools/gazelle/*, owned by both lint and
    # publish) is listed under each, so it lands here twice when both are selected.
    # De-dupe — order-preserving — so the scaffolder copies/filters it once.
    resolved.copy = _dedupe(resolved.copy)
    resolved.directories = _dedupe(resolved.directories)
    resolved.composite = _dedupe(resolved.composite)
    return resolved


def _dedupe(items: list[str]) -> list[str]:
    """Drop duplicates while preserving first-occurrence order."""
    return list(dict.fromkeys(items))


def compute_prune_set(
    manifest: BootstrapManifest,
    old_languages: set[str],
    old_features: set[str],
    new_languages: set[str],
    new_features: set[str],
) -> set[str]:
    """Relative paths the old selection shipped that the new one no longer does.

    On a re-bootstrap where the user drops a language or feature, the scaffolder
    (which only ever *writes* files) would leave that owner's artifacts orphaned
    on disk — referencing things ``MODULE.bazel`` no longer declares. This is the
    set those orphans are drawn from. Two manifest-driven differences, unioned:

    * ``owned`` — files/dirs/composite the old selection resolved but the new one
      does not. It spans **all three** categories so an owner-exclusive
      *composite* file (e.g. ``.publish.toml``, ``tools/rust/Cargo.toml``) is
      caught, while an *always-shipped* composite (``MODULE.bazel``) — present
      under both selections — is not (it is merely re-rendered, not deleted).
    * ``gated`` — files newly excluded via ``[exclude.when_feature_absent]``.
      These can be sub-paths of a still-shipped directory
      (``tools/cpp/toolchains`` lives under the surviving ``tools/cpp``), which
      the ``owned`` directory-level difference cannot see.

    Pure: returns relative path strings and never touches the filesystem, so the
    caller decides which actually exist before deleting.
    """
    old = resolve_files(manifest, old_languages, old_features)
    new = resolve_files(manifest, new_languages, new_features)

    def _shipped(resolved: ResolvedFiles) -> set[str]:
        return {*resolved.copy, *resolved.directories, *resolved.composite}

    owned = _shipped(old) - _shipped(new)
    gated = effective_excluded_files(manifest, new_features) - effective_excluded_files(manifest, old_features)
    return owned | gated


def _git(source_root: Path, *args: str) -> str | None:
    """Run a read-only git command in *source_root*, or None if it can't."""
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "-C", str(source_root), *args],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    return result.stdout.strip()


def starter_revision(source_root: Path) -> str | None:
    """The starter checkout's HEAD, ``-dirty`` when it has uncommitted changes.

    None when *source_root* is not a git checkout (or git is unavailable) —
    a scaffold from a tarball is legitimate, so the field is simply omitted
    rather than recorded as a guess.
    """
    head = _git(source_root, "rev-parse", "HEAD")
    if not head:
        return None
    return f"{head}-dirty" if _git(source_root, "status", "--porcelain") else head


def file_fingerprint(path: Path) -> str | None:
    """What the inventory records for *path*: ``sha256:<hex>`` of a file's
    bytes, ``symlink:<target>`` for a symlink, None when it is neither."""
    if path.is_symlink():
        return f"symlink:{path.readlink()}"
    if not path.is_file():
        return None
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def write_bootstrap_marker(
    target_path: Path,
    module_dir: str,
    languages: set[str],
    features: set[str],
    source_root: Path | None = None,
    files: Iterable[str] | None = None,
    orphans: dict[str, str] | None = None,
) -> None:
    """Record the scaffolded selection in ``BOOTSTRAP_MARKER_FILE``.

    Written on every (re-)bootstrap so :func:`read_bootstrap_marker` can recover
    the exact ``module_dir`` / languages / features a later run needs — no
    filesystem guessing. The repo *name* is intentionally not stored here; it
    stays authoritative in ``MODULE.bazel``.

    ``bootstrapped_at`` and ``starter_revision`` record when the scaffold was
    last written and from which starter commit. Nothing reads them back — they
    answer "how far behind the starter is this repo?" when a generated file
    turns out to predate a starter change. ``starter_revision`` is omitted when
    *source_root* is absent or is not a git checkout.

    *files* are the relative paths this run manages. Each one present on disk
    goes into a ``[files]`` table with its :func:`file_fingerprint` as of this
    call, so a later run can tell which files the starter stopped shipping and
    whether one changed since. Omitted, no table is written.

    *orphans* (see :func:`compute_orphans`) go into an ``[orphans]`` table with
    the fingerprint they were last recorded with, not their current one. The
    marker has to carry them: the next run's ``[files]`` no longer lists them,
    so an orphan left on disk would otherwise be forgotten one run later.
    """
    langs = ", ".join(f'"{x}"' for x in sorted(languages))
    feats = ", ".join(f'"{x}"' for x in sorted(features))
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    revision = starter_revision(source_root) if source_root else None
    content = (
        f"# {BOOTSTRAP_MARKER_FILE} — written by the bootstrap tool so a re-bootstrap\n"
        "# recovers this repo's selection exactly. Rewritten on each re-bootstrap;\n"
        "# edit only if you know what you're doing.\n"
        "[repo]\n"
        f'module_dir = "{module_dir}"\n'
        f"languages = [{langs}]\n"
        f"features = [{feats}]\n"
        f'bootstrapped_at = "{stamp}"\n'
    )
    if revision:
        content += f'starter_revision = "{revision}"\n'
    if files is not None:
        content += "\n# Every file the bootstrap tool manages, as it left them.\n[files]\n"
        for rel in sorted(set(files)):
            fingerprint = file_fingerprint(target_path / rel)
            if fingerprint:
                # JSON string escapes are TOML basic-string escapes too.
                content += f"{json.dumps(rel, ensure_ascii=False)} = {json.dumps(fingerprint, ensure_ascii=False)}\n"
    if orphans:
        content += "\n# Files the starter no longer ships that are still on disk.\n[orphans]\n"
        for rel, fingerprint in sorted(orphans.items()):
            content += f"{json.dumps(rel, ensure_ascii=False)} = {json.dumps(fingerprint, ensure_ascii=False)}\n"
    (target_path / BOOTSTRAP_MARKER_FILE).write_text(content)


def _read_marker_table(target_path: Path, table: str) -> dict[str, str] | None:
    """A path -> fingerprint table of the marker, or None when the marker is
    absent, unparseable, or has no such table."""
    path = target_path / BOOTSTRAP_MARKER_FILE
    if not path.is_file():
        return None
    try:
        entries = tomllib.loads(path.read_text()).get(table)
    except (tomllib.TOMLDecodeError, OSError):
        return None
    if not isinstance(entries, dict):
        return None
    return {rel: fp for rel, fp in entries.items() if isinstance(fp, str)}


def read_bootstrap_inventory(target_path: Path) -> dict[str, str] | None:
    """The marker's ``[files]`` table (path -> fingerprint), or None.

    None when the marker is absent, unparseable, or predates the inventory, so
    a caller can tell "nothing recorded yet" from "recorded, and empty".
    """
    return _read_marker_table(target_path, "files")


def read_bootstrap_orphans(target_path: Path) -> dict[str, str]:
    """The marker's ``[orphans]`` table (path -> last recorded fingerprint)."""
    return _read_marker_table(target_path, "orphans") or {}


def compute_orphans(
    target_path: Path,
    module_dir: str,
    old_files: dict[str, str],
    old_orphans: dict[str, str],
    new_files: Iterable[str],
) -> dict[str, str]:
    """Files an earlier run managed that this run does not, still on disk.

    Maps each path to the fingerprint it was last recorded with, so
    :func:`orphan_is_modified` can tell whether it changed since. Covers both a
    file the starter stopped shipping (or renamed) and one a deselected owner
    left behind. *old_orphans* are carried forward until they are deleted, leave
    the disk, or ship again. Nothing under *module_dir* is ever reported: that
    tree is the user's.
    """
    shipped = set(new_files)
    orphans: dict[str, str] = {}
    for rel, fingerprint in {**old_orphans, **old_files}.items():
        if rel in shipped or rel == module_dir or rel.startswith(f"{module_dir}/"):
            continue
        if file_fingerprint(target_path / rel) is None:
            continue
        orphans[rel] = fingerprint
    return orphans


def orphan_is_modified(target_path: Path, rel: str, recorded: str) -> bool:
    """True when *rel* no longer matches the fingerprint the tool recorded.

    "Modified" means "differs from what the bootstrap left", which a formatter
    or a dependency bot causes as readily as a hand edit.
    """
    return file_fingerprint(target_path / rel) != recorded


def read_bootstrap_marker(
    target_path: Path,
    manifest: BootstrapManifest,
) -> tuple[set[str], set[str], str] | None:
    """Read ``(languages, features, module_dir)`` from the marker, or None.

    Returns None when the marker is absent or unparseable so the caller can
    treat the repo as un-detected (ask the user) rather than guess. Languages
    and features are intersected with the manifest's known keys, so a stale or
    hand-edited entry can't smuggle in an unknown owner.
    """
    path = target_path / BOOTSTRAP_MARKER_FILE
    if not path.is_file():
        return None
    try:
        repo = tomllib.loads(path.read_text()).get("repo", {})
    except (tomllib.TOMLDecodeError, OSError):
        return None
    module_dir = repo.get("module_dir") or manifest.default_module_dir
    languages = {x for x in repo.get("languages", []) if x in manifest.languages}
    features = {x for x in repo.get("features", []) if x in manifest.features}
    return languages, features, module_dir
