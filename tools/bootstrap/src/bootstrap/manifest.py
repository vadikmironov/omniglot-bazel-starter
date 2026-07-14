"""Bootstrap manifest loader.

Parses bootstrap_manifest.toml and resolves the set of files to include
in a new repository based on the user's language selection.
"""

from dataclasses import dataclass, field
from pathlib import Path

import tomllib

# Marker file written into every scaffolded repo, recording the selection so a
# re-bootstrap recovers it exactly instead of inferring it from the filesystem.
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


def write_bootstrap_marker(
    target_path: Path,
    module_dir: str,
    languages: set[str],
    features: set[str],
) -> None:
    """Record the scaffolded selection in ``BOOTSTRAP_MARKER_FILE``.

    Written on every (re-)bootstrap so :func:`read_bootstrap_marker` can recover
    the exact ``module_dir`` / languages / features a later run needs — no
    filesystem guessing. The repo *name* is intentionally not stored here; it
    stays authoritative in ``MODULE.bazel``.
    """
    langs = ", ".join(f'"{x}"' for x in sorted(languages))
    feats = ", ".join(f'"{x}"' for x in sorted(features))
    content = (
        f"# {BOOTSTRAP_MARKER_FILE} — written by the bootstrap tool so a re-bootstrap\n"
        "# recovers this repo's selection exactly. Rewritten on each re-bootstrap;\n"
        "# edit only if you know what you're doing.\n"
        "[repo]\n"
        f'module_dir = "{module_dir}"\n'
        f"languages = [{langs}]\n"
        f"features = [{feats}]\n"
    )
    (target_path / BOOTSTRAP_MARKER_FILE).write_text(content)


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
