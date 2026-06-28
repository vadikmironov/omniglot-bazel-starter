"""Unit tests for bootstrap.manifest — TOML loading and file resolution."""

import tempfile
import unittest
from pathlib import Path

from bootstrap.manifest import (
    BootstrapManifest,
    effective_excluded_files,
    effective_languages,
    load_manifest,
    resolve_files,
)

# All language keys defined in the manifest.
ALL_LANGUAGES = {"python", "cpp", "rust", "java", "go"}

# Expected labels for each language.
EXPECTED_LABELS = {
    "python": "Python",
    "cpp": "C++",
    "rust": "Rust",
    "java": "Java",
    "go": "Go",
}

# Palantir file that should always be excluded.
PALANTIR_FILE = "tools/format/src/main/java/monorepo/test/PalantirJavaFormatWrapper.java"


def _manifest_path() -> Path:
    """Locate the real bootstrap_manifest.toml via runfiles."""
    return Path(__file__).resolve().parent.parent / "bootstrap_manifest.toml"


class TestLoadManifest(unittest.TestCase):
    """Tests for load_manifest() against the real manifest file."""

    manifest: BootstrapManifest

    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load_manifest(_manifest_path())

    def test_load_manifest_structure(self) -> None:
        """All top-level fields are populated and have correct types."""
        m = self.manifest
        self.assertIsInstance(m.default_module_dir, str)
        self.assertIsInstance(m.languages, dict)
        self.assertIsInstance(m.core_files, list)
        self.assertIsInstance(m.core_directories, list)
        self.assertIsInstance(m.language_files, dict)
        self.assertIsInstance(m.composite_files, list)
        self.assertIsInstance(m.composite_language_files, dict)
        self.assertIsInstance(m.excluded_files, list)
        self.assertIsInstance(m.excluded_when_feature_absent, dict)
        self.assertIsInstance(m.original_name, str)

    def test_default_module_dir(self) -> None:
        self.assertEqual(self.manifest.default_module_dir, "modules")

    def test_languages_all_present(self) -> None:
        """Exactly the expected 5 languages are defined with correct labels."""
        self.assertEqual(set(self.manifest.languages.keys()), ALL_LANGUAGES)
        for key, expected_label in EXPECTED_LABELS.items():
            self.assertEqual(self.manifest.languages[key].label, expected_label)

    def test_language_files_and_directories(self) -> None:
        """Each language has non-empty files and directories lists."""
        for lang_key, config in self.manifest.languages.items():
            with self.subTest(lang=lang_key):
                self.assertTrue(
                    len(config.files) > 0,
                    f"{lang_key} should have at least one config file",
                )
                self.assertTrue(
                    len(config.directories) > 0,
                    f"{lang_key} should have at least one tool directory",
                )

    def test_core_files_nonempty(self) -> None:
        self.assertTrue(len(self.manifest.core_files) > 0)
        self.assertIn(".bazelversion", self.manifest.core_files)
        self.assertIn("WORKSPACE.bazel", self.manifest.core_files)

    def test_core_directories(self) -> None:
        # tools/publish is now gated on the [features.publish] selection,
        # not unconditional.
        self.assertNotIn("tools/publish", self.manifest.core_directories)

    def test_publish_feature(self) -> None:
        """The publish feature is declared with go as a required language."""
        self.assertIn("publish", self.manifest.features)
        feat = self.manifest.features["publish"]
        self.assertEqual(feat.requires, ["go"])
        self.assertIn("tools/publish", feat.directories)
        self.assertIn(".publish.toml", feat.composite_files)
        # tools/publish/BUILD is section-filtered so its ruff lint_test is gated.
        self.assertIn("tools/publish/BUILD", feat.composite_files)
        # The shared gazelle vocabulary is owned by lint OR publish, so it is
        # enumerated under both features (see test_lint_feature for the lint side).
        self.assertIn("tools/gazelle/directives/directives.go", feat.composite_files)
        self.assertIn("tools/gazelle/vocab/vocab.go", feat.composite_files)

    def test_lint_feature(self) -> None:
        """The lint feature owns the linter aspect files and the gazelle extension.

        The gazelle subdir is enumerated as composite files (not a verbatim
        `directories` copy) so its per-language sections are filtered. The
        single-language generators live in the feature's composite_language_files
        so each ships only with its language.
        """
        self.assertIn("lint", self.manifest.features)
        feat = self.manifest.features["lint"]
        self.assertEqual(feat.requires, ["go"])
        # No verbatim directory copy — that would leak unfiltered lang: markers.
        self.assertEqual(feat.directories, [])
        self.assertIn("tools/lint/linters.bzl", feat.composite_files)
        self.assertIn("tools/lint/BUILD", feat.composite_files)
        # Marker-free contract + the multi-language (filtered) gazelle files.
        for f in (
            "tools/lint/gazelle/lang.go",
            "tools/lint/gazelle/BUILD",
            "tools/lint/gazelle/kinds.go",
            "tools/lint/gazelle/generate.go",
        ):
            self.assertIn(f, feat.composite_files)
        # The shared gazelle vocabulary (//tools/gazelle) is depended on by every
        # generator's gazelle_binary, so it ships under lint OR publish — listed
        # identically under both features (de-duped by resolve_files).
        for f in (
            "tools/gazelle/directives/directives.go",
            "tools/gazelle/directives/BUILD",
            "tools/gazelle/vocab/vocab.go",
            "tools/gazelle/vocab/BUILD",
        ):
            self.assertIn(f, feat.composite_files)
        # Single-language generators are gated on feature AND language.
        clf = feat.composite_language_files
        self.assertEqual(clf.get("cpp"), ["tools/lint/gazelle/cpp.go"])
        self.assertEqual(clf.get("rust"), ["tools/lint/gazelle/rust.go"])
        self.assertEqual(clf.get("java"), ["tools/lint/gazelle/java.go"])
        self.assertEqual(clf.get("python"), ["tools/lint/gazelle/python.go"])
        # Marker-free raw-copy gated on feature AND language: the rust clippy gate.
        self.assertEqual(feat.language_files.get("rust"), ["tools/lint/clippy_assert_empty.sh"])

    def test_remote_cache_feature(self) -> None:
        """remote_cache is a file-less feature that gates BuildBuddy wiring via markers."""
        self.assertIn("remote_cache", self.manifest.features)
        feat = self.manifest.features["remote_cache"]
        self.assertEqual(feat.requires, [])
        self.assertEqual(feat.files, [])
        self.assertEqual(feat.directories, [])
        self.assertEqual(feat.composite_files, [])
        self.assertEqual(feat.composite_language_files, {})
        # It owns no conditional excludes either — purely marker-gated.
        self.assertNotIn("remote_cache", self.manifest.excluded_when_feature_absent)

    def test_feature_conditional_excludes(self) -> None:
        """Lint-only static-analysis artifacts are registered for conditional drop."""
        absent = self.manifest.excluded_when_feature_absent
        self.assertIn("lint", absent)
        self.assertIn(".mypy.ini", absent["lint"])
        self.assertIn(".nogo_config.json", absent["lint"])
        self.assertIn(".pmd.xml", absent["lint"])
        self.assertIn(".spotbugs-exclude.xml", absent["lint"])
        self.assertIn("tools/python/mypy", absent["lint"])
        # C++/Rust lint configs are intentionally NOT feature-gated.
        self.assertNotIn(".clang-tidy", absent["lint"])
        self.assertNotIn(".clippy.toml", absent["lint"])

    def test_custom_toolchains_feature(self) -> None:
        """The custom_toolchains feature exists, requires no language, and drops
        the three per-language toolchain dirs when absent."""
        self.assertIn("custom_toolchains", self.manifest.features)
        feat = self.manifest.features["custom_toolchains"]
        self.assertEqual(feat.requires, [])
        # No owned files/dirs/composites — it gates via markers + excludes only.
        self.assertEqual(feat.directories, [])
        self.assertEqual(feat.files, [])
        self.assertEqual(feat.composite_files, [])
        absent = self.manifest.excluded_when_feature_absent
        self.assertIn("custom_toolchains", absent)
        for d in ("tools/cpp/toolchains", "tools/go/toolchains", "tools/java/toolchains"):
            self.assertIn(d, absent["custom_toolchains"])
        # cpp_segment is section-filtered so its host register block can be gated.
        self.assertIn("tools/cpp/cpp_segment.MODULE.bazel", self.manifest.composite_language_files.get("cpp", []))

    def test_composite_files_list(self) -> None:
        """All known always-shipped composite files are present.

        .publish.toml is intentionally absent: it now ships as part of the
        [features.publish] entry. tools/lint/linters.bzl and tools/lint/BUILD are
        likewise absent: they moved to [features.lint].composite_files.
        .clang-format and .pre-commit-config.yaml are absent too: they moved to
        [composite_language_files] (cpp/java and python respectively) so they are
        not shipped for selections that wouldn't use them.
        """
        expected = {
            "MODULE.bazel",
            ".bazelrc",
            "BUILD",
            ".gitignore",
            "tools/format/BUILD",
            "user.bazelrc.template",
        }
        self.assertEqual(set(self.manifest.composite_files), expected)

    def test_composite_language_files(self) -> None:
        """Language-specific composite files are present."""
        clf = self.manifest.composite_language_files
        self.assertIn("tools/python/requirements.in", clf.get("python", []))
        self.assertIn("tools/cpp/cpp_3rd_party_dependencies.MODULE.bazel", clf.get("cpp", []))
        self.assertIn("tools/rust/Cargo.toml", clf.get("rust", []))
        self.assertIn("tools/java/package_defs.bzl", clf.get("java", []))
        self.assertIn("tools/java/java_segment.MODULE.bazel", clf.get("java", []))
        self.assertIn("go.mod", clf.get("go", []))
        self.assertIn("tools/go/go_segment.MODULE.bazel", clf.get("go", []))
        # pre-commit is installed from the Python .venv, so it rides with Python.
        self.assertIn(".pre-commit-config.yaml", clf.get("python", []))
        # clang-format formats C++ and Java only — keyed by the cpp,java OR-tag.
        self.assertIn(".clang-format", clf.get("cpp,java", []))

    def test_excluded_files(self) -> None:
        self.assertIn(PALANTIR_FILE, self.manifest.excluded_files)

    def test_original_name(self) -> None:
        self.assertEqual(self.manifest.original_name, "omniglot-bazel-starter")


class TestResolveFiles(unittest.TestCase):
    """Tests for resolve_files() — file resolution based on language selection."""

    manifest: BootstrapManifest

    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load_manifest(_manifest_path())

    def test_resolve_python_only(self) -> None:
        """Selecting only Python includes python files but not other languages."""
        resolved = resolve_files(self.manifest, {"python"})

        # Python-specific files present (.ruff.toml is composite-routed for section filtering)
        self.assertIn(".ruff.toml", resolved.composite)
        self.assertIn("tools/python", resolved.directories)
        # .mypy.ini is lint-gated (feature-conditional exclude): absent without
        # lint, present once lint is also selected.
        self.assertNotIn(".mypy.ini", resolved.copy)
        self.assertIn(".mypy.ini", resolve_files(self.manifest, {"python"}, {"lint"}).copy)

        # Other languages absent
        self.assertNotIn(".clang-tidy", resolved.copy)
        self.assertNotIn(".rustfmt.toml", resolved.copy)
        self.assertNotIn(".pmd.xml", resolved.copy)
        self.assertNotIn("tools/cpp", resolved.directories)
        self.assertNotIn("tools/rust", resolved.directories)
        self.assertNotIn("tools/java", resolved.directories)
        self.assertNotIn("tools/go", resolved.directories)

    def test_resolve_all_languages(self) -> None:
        """Selecting all languages (with lint, which owns the per-language
        analysis configs) includes every language file."""
        resolved = resolve_files(self.manifest, ALL_LANGUAGES, {"lint"})

        # All language files present
        for lang_key, config in self.manifest.languages.items():
            for f in config.files:
                self.assertIn(f, resolved.copy, f"{f} missing for {lang_key}")
            for d in config.directories:
                self.assertIn(d, resolved.directories, f"{d} missing for {lang_key}")

        # Core files present
        for f in self.manifest.core_files:
            self.assertIn(f, resolved.copy, f"core file {f} missing")

        # Core directories present
        for d in self.manifest.core_directories:
            self.assertIn(d, resolved.directories, f"core dir {d} missing")

    def test_resolve_core_always_included(self) -> None:
        """Core files and directories appear regardless of which language is selected."""
        for lang in ALL_LANGUAGES:
            resolved = resolve_files(self.manifest, {lang})
            for f in self.manifest.core_files:
                self.assertIn(f, resolved.copy, f"core file {f} missing with {lang}")
            for d in self.manifest.core_directories:
                self.assertIn(d, resolved.directories, f"core dir {d} missing with {lang}")

    def test_resolve_no_excluded_in_copy(self) -> None:
        """Excluded files never appear in resolved.copy, even with all langs."""
        resolved = resolve_files(self.manifest, ALL_LANGUAGES)
        for f in self.manifest.excluded_files:
            self.assertNotIn(f, resolved.copy, f"excluded file {f} in copy")

    def test_resolve_language_files_java(self) -> None:
        """Java language_files included when java selected, absent otherwise."""
        java_lang_files = self.manifest.language_files.get("java", [])
        self.assertTrue(len(java_lang_files) > 0, "expected java language_files")

        # With java selected
        resolved = resolve_files(self.manifest, {"java"})
        for f in java_lang_files:
            if f not in self.manifest.excluded_files:
                self.assertIn(f, resolved.copy, f"{f} missing with java")

        # Without java selected
        resolved = resolve_files(self.manifest, {"python"})
        for f in java_lang_files:
            self.assertNotIn(f, resolved.copy, f"{f} present without java")

    def test_resolve_directories_per_language(self) -> None:
        """Each language's directories appear only when that language is selected."""
        for lang in ALL_LANGUAGES:
            config = self.manifest.languages[lang]
            # Selected — directories present
            resolved = resolve_files(self.manifest, {lang})
            for d in config.directories:
                self.assertIn(d, resolved.directories)

            # Not selected — directories absent
            others = ALL_LANGUAGES - {lang}
            resolved = resolve_files(self.manifest, others)
            for d in config.directories:
                self.assertNotIn(d, resolved.directories)

    def test_resolve_composite_always_present(self) -> None:
        """Composite files are always in resolved.composite regardless of selection."""
        for lang in ALL_LANGUAGES:
            resolved = resolve_files(self.manifest, {lang})
            for f in self.manifest.composite_files:
                if f not in self.manifest.excluded_files:
                    self.assertIn(
                        f,
                        resolved.composite,
                        f"composite {f} missing with {lang}",
                    )

    def test_resolve_composite_language_files(self) -> None:
        """Language-specific composite files only appear when language is selected."""
        # Go selected — go.mod should be in composite
        resolved = resolve_files(self.manifest, {"go"})
        self.assertIn("go.mod", resolved.composite)
        self.assertIn("tools/go/go_segment.MODULE.bazel", resolved.composite)

        # Go not selected — go.mod should NOT be in composite
        resolved = resolve_files(self.manifest, {"python"})
        self.assertNotIn("go.mod", resolved.composite)
        self.assertNotIn("tools/go/go_segment.MODULE.bazel", resolved.composite)
        # Python selected — .ruff.toml should be in composite (not plain copy)
        self.assertIn(".ruff.toml", resolved.composite)
        self.assertNotIn(".ruff.toml", resolved.copy)

    def test_resolve_feature_language_files(self) -> None:
        """A feature's per-language raw-copy file ships only when feature AND language match."""
        script = "tools/lint/clippy_assert_empty.sh"
        # lint + rust → shipped as a plain copy (not composite).
        resolved = resolve_files(self.manifest, {"rust"}, {"lint"})
        self.assertIn(script, resolved.copy)
        self.assertNotIn(script, resolved.composite)
        # lint without rust, and rust without lint → absent.
        self.assertNotIn(script, resolve_files(self.manifest, {"python"}, {"lint"}).copy)
        self.assertNotIn(script, resolve_files(self.manifest, {"rust"}, set()).copy)

    def test_resolve_clang_format_gated_on_cpp_or_java(self) -> None:
        """.clang-format ships when C++ or Java is selected, and only then."""
        self.assertIn(".clang-format", resolve_files(self.manifest, {"cpp"}).composite)
        self.assertIn(".clang-format", resolve_files(self.manifest, {"java"}).composite)
        self.assertIn(".clang-format", resolve_files(self.manifest, {"cpp", "java"}).composite)
        for sel in ({"python"}, {"rust"}, {"go"}, {"python", "rust", "go"}):
            self.assertNotIn(".clang-format", resolve_files(self.manifest, sel).composite, f"clang-format with {sel}")

    def test_resolve_precommit_gated_on_python(self) -> None:
        """.pre-commit-config.yaml ships only when Python is selected."""
        self.assertIn(".pre-commit-config.yaml", resolve_files(self.manifest, {"python"}).composite)
        for sel in ({"cpp"}, {"java"}, {"rust"}, {"go"}, {"cpp", "java", "rust", "go"}):
            self.assertNotIn(
                ".pre-commit-config.yaml", resolve_files(self.manifest, sel).composite, f"pre-commit with {sel}"
            )

    def test_resolve_gazelle_vocab_gated_on_lint_or_publish(self) -> None:
        """The shared gazelle vocabulary ships when lint OR publish is selected,
        is absent for neither, and is never duplicated when both are on."""
        gazelle_files = [
            "tools/gazelle/directives/directives.go",
            "tools/gazelle/directives/BUILD",
            "tools/gazelle/vocab/vocab.go",
            "tools/gazelle/vocab/BUILD",
        ]
        # Present under either feature alone, and under both.
        for feats in ({"lint"}, {"publish"}, {"lint", "publish"}):
            composite = resolve_files(self.manifest, {"python", "go"}, feats).composite
            for f in gazelle_files:
                self.assertIn(f, composite, f"{f} missing with {feats}")
                # Listed under both features — must still appear exactly once.
                self.assertEqual(composite.count(f), 1, f"{f} duplicated with {feats}")
        # Absent when neither feature is selected.
        composite = resolve_files(self.manifest, {"python", "go"}, {"remote_cache"}).composite
        for f in gazelle_files:
            self.assertNotIn(f, composite, f"{f} present without lint/publish")

    def test_resolve_setup_dir_always_shipped(self) -> None:
        """tools/setup (the Bazelisk installer) is a core directory for any selection."""
        self.assertIn("tools/setup", self.manifest.core_directories)
        for lang in ALL_LANGUAGES:
            self.assertIn("tools/setup", resolve_files(self.manifest, {lang}).directories)

    def test_effective_excluded_custom_toolchains(self) -> None:
        """The per-language toolchain dirs are excluded without custom_toolchains,
        kept with it."""
        dirs = ("tools/cpp/toolchains", "tools/go/toolchains", "tools/java/toolchains")
        without = effective_excluded_files(self.manifest, set())
        for d in dirs:
            self.assertIn(d, without)
        with_ct = effective_excluded_files(self.manifest, {"custom_toolchains"})
        for d in dirs:
            self.assertNotIn(d, with_ct)

    def test_effective_excluded_files_feature_conditional(self) -> None:
        """Lint artifacts are excluded without lint, kept with it; the
        unconditional excludes apply either way."""
        without = effective_excluded_files(self.manifest, set())
        self.assertIn(".mypy.ini", without)
        self.assertIn(".nogo_config.json", without)
        self.assertIn("tools/python/mypy", without)

        with_lint = effective_excluded_files(self.manifest, {"lint"})
        self.assertNotIn(".mypy.ini", with_lint)
        self.assertNotIn(".nogo_config.json", with_lint)
        self.assertNotIn("tools/python/mypy", with_lint)

        # Unconditional excludes are present regardless of features.
        self.assertIn(PALANTIR_FILE, without)
        self.assertIn(PALANTIR_FILE, with_lint)

    def test_resolve_go_excludes_nogo_config_without_lint(self) -> None:
        """.nogo_config.json (a Go language file) ships only when lint is on too."""
        self.assertNotIn(".nogo_config.json", resolve_files(self.manifest, {"go"}).copy)
        self.assertIn(".nogo_config.json", resolve_files(self.manifest, {"go"}, {"lint"}).copy)

    def test_resolve_empty_selection(self) -> None:
        """Empty language set still gets core files, core dirs, and composites."""
        resolved = resolve_files(self.manifest, set())
        # Core files present
        for f in self.manifest.core_files:
            self.assertIn(f, resolved.copy)
        # Core directories present
        for d in self.manifest.core_directories:
            self.assertIn(d, resolved.directories)
        # Composites present
        self.assertTrue(len(resolved.composite) > 0)
        # Only core directories, no language directories
        self.assertEqual(len(resolved.directories), len(self.manifest.core_directories))


class TestFeaturesPlumbing(unittest.TestCase):
    """Generic plumbing for the [features] manifest section.

    These tests use synthetic manifests so they remain green before any
    real feature is defined in bootstrap_manifest.toml.
    """

    def _load_synthetic(self) -> BootstrapManifest:
        toml_content = """\
[repo]
default_module_dir = "src"

[core]
files = ["README.md"]

[languages.alpha]
label = "Alpha"
directories = ["tools/alpha"]

[languages.beta]
label = "Beta"
directories = ["tools/beta"]

[composite]
files = ["root.bzl"]

[features.shipit]
label = "Shipit"
requires = ["alpha"]
directories = ["tools/shipit"]
files = [".shipit.toml"]
composite_files = ["tools/shipit/MODULE.bazel"]

[substitutions]
original_name = "my_project"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            tmp_path = Path(f.name)
        self.addCleanup(tmp_path.unlink)
        return load_manifest(tmp_path)

    def test_features_parsed(self) -> None:
        m = self._load_synthetic()
        self.assertIn("shipit", m.features)
        feat = m.features["shipit"]
        self.assertEqual(feat.label, "Shipit")
        self.assertEqual(feat.requires, ["alpha"])
        self.assertEqual(feat.directories, ["tools/shipit"])
        self.assertEqual(feat.files, [".shipit.toml"])
        self.assertEqual(feat.composite_files, ["tools/shipit/MODULE.bazel"])

    def test_features_default_to_empty_when_section_missing(self) -> None:
        toml_content = """\
[repo]
default_module_dir = "src"

[core]
files = []

[composite]
files = []

[substitutions]
original_name = "x"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            tmp_path = Path(f.name)
        self.addCleanup(tmp_path.unlink)
        m = load_manifest(tmp_path)
        self.assertEqual(m.features, {})

    def test_effective_languages_promotes_required(self) -> None:
        m = self._load_synthetic()
        result = effective_languages(m, {"beta"}, {"shipit"})
        self.assertEqual(result, {"alpha", "beta"})

    def test_effective_languages_no_features(self) -> None:
        m = self._load_synthetic()
        result = effective_languages(m, {"beta"}, set())
        self.assertEqual(result, {"beta"})

    def test_resolve_with_feature_pulls_required_language(self) -> None:
        m = self._load_synthetic()
        # User picks beta but selects shipit which requires alpha.
        resolved = resolve_files(m, {"beta"}, {"shipit"})
        # Alpha's directory was auto-promoted in.
        self.assertIn("tools/alpha", resolved.directories)
        self.assertIn("tools/beta", resolved.directories)
        # Feature's own directory, file, composite_file all included.
        self.assertIn("tools/shipit", resolved.directories)
        self.assertIn(".shipit.toml", resolved.copy)
        self.assertIn("tools/shipit/MODULE.bazel", resolved.composite)

    def test_resolve_without_feature_omits_feature_assets(self) -> None:
        m = self._load_synthetic()
        resolved = resolve_files(m, {"alpha", "beta"})  # no features
        self.assertNotIn("tools/shipit", resolved.directories)
        self.assertNotIn(".shipit.toml", resolved.copy)
        self.assertNotIn("tools/shipit/MODULE.bazel", resolved.composite)


class TestSyntheticManifest(unittest.TestCase):
    """Test load_manifest with a programmatically created TOML file."""

    def test_synthetic_manifest(self) -> None:
        """A minimal synthetic manifest loads correctly."""
        toml_content = """\
[repo]
default_module_dir = "src"

[core]
files = ["README.md"]

[languages.alpha]
label = "Alpha"
files = ["alpha.cfg"]
directories = ["tools/alpha"]

[languages.beta]
label = "Beta"
files = ["beta.cfg"]
directories = ["tools/beta"]

[language_files]
alpha = ["shared/alpha_helper.sh"]

[composite]
files = ["config.bzl"]

[exclude]
files = ["old_readme.md"]

[substitutions]
original_name = "my_project"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            tmp_path = Path(f.name)

        try:
            m = load_manifest(tmp_path)
            self.assertEqual(m.default_module_dir, "src")
            self.assertEqual(set(m.languages.keys()), {"alpha", "beta"})
            self.assertEqual(m.languages["alpha"].label, "Alpha")
            self.assertEqual(m.core_files, ["README.md"])
            self.assertEqual(m.composite_files, ["config.bzl"])
            self.assertEqual(m.excluded_files, ["old_readme.md"])
            self.assertEqual(m.original_name, "my_project")

            # Resolve with alpha only
            resolved = resolve_files(m, {"alpha"})
            self.assertIn("README.md", resolved.copy)
            self.assertIn("alpha.cfg", resolved.copy)
            self.assertIn("shared/alpha_helper.sh", resolved.copy)
            self.assertNotIn("beta.cfg", resolved.copy)
            self.assertIn("tools/alpha", resolved.directories)
            self.assertNotIn("tools/beta", resolved.directories)
            self.assertIn("config.bzl", resolved.composite)
        finally:
            tmp_path.unlink()


if __name__ == "__main__":
    unittest.main()
