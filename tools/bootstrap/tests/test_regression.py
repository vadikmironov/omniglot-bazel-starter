"""Regression tests — manifest and source repository consistency.

These tests verify that the bootstrap manifest stays in sync with the
actual repository files and section markers as the codebase evolves.
They catch:
  - Files referenced in the manifest that no longer exist
  - Composite files with unbalanced or orphaned markers
  - Marker tags that reference unknown languages
  - Key composite files missing expected language sections
"""

import re
import unittest
from pathlib import Path

from bootstrap.manifest import (
    BootstrapManifest,
    effective_excluded_files,
    load_manifest,
    resolve_files,
)
from bootstrap.processor import filter_sections, has_user_region

# Expected language keys — any change here is intentional.
EXPECTED_LANGUAGES = {"python", "cpp", "rust", "java", "go"}

# Regex patterns matching section markers (mirror processor._BEGIN_RE / _END_RE)
_BEGIN_RE = re.compile(r"^\s*#\s*---\s*BEGIN\s+((?:lang|feature):\S+|exclude)\s*---\s*$", re.MULTILINE)
_END_RE = re.compile(r"^\s*#\s*---\s*END\s+((?:lang|feature):\S+|exclude)\s*---\s*$", re.MULTILINE)

# `exports_files([...])` with a literal list (glob() forms are skipped) and the
# quoted filenames inside it — used to verify exported siblings are shipped.
_EXPORTS_RE = re.compile(r"exports_files\(\s*\[([^\]]*)\]")
_QUOTED_RE = re.compile(r"""["']([^"']+)["']""")


def _exported_filenames(content: str) -> list[str]:
    """Package-relative names exported via ``exports_files([...])`` in *content*."""
    names: list[str] = []
    for match in _EXPORTS_RE.finditer(content):
        names.extend(_QUOTED_RE.findall(match.group(1)))
    return names


def _find_source_root() -> Path:
    """Locate the monorepo root by walking up from this test file."""
    return Path(__file__).resolve().parents[3]


class TestManifestFilesExist(unittest.TestCase):
    """Every file and directory referenced in the manifest must exist."""

    source_root: Path
    manifest: BootstrapManifest

    @classmethod
    def setUpClass(cls) -> None:
        cls.source_root = _find_source_root()
        cls.manifest = load_manifest(cls.source_root / "tools" / "bootstrap" / "bootstrap_manifest.toml")

    def test_all_core_files_exist(self) -> None:
        for f in self.manifest.core_files:
            path = self.source_root / f
            self.assertTrue(
                path.exists() or path.is_symlink(),
                f"core file missing: {f}",
            )

    def test_all_language_files_exist(self) -> None:
        for lang, config in self.manifest.languages.items():
            for f in config.files:
                self.assertTrue(
                    (self.source_root / f).exists(),
                    f"language file missing: {f} ({lang})",
                )

    def test_all_core_directories_exist(self) -> None:
        for d in self.manifest.core_directories:
            self.assertTrue(
                (self.source_root / d).is_dir(),
                f"core directory missing: {d}",
            )

    def test_all_language_directories_exist(self) -> None:
        for lang, config in self.manifest.languages.items():
            for d in config.directories:
                self.assertTrue(
                    (self.source_root / d).is_dir(),
                    f"language directory missing: {d} ({lang})",
                )

    def test_all_language_files_entries_exist(self) -> None:
        for tag, files in self.manifest.language_files.items():
            for f in files:
                self.assertTrue(
                    (self.source_root / f).exists(),
                    f"language_files entry missing: {f} (tag={tag})",
                )

    def test_all_composite_files_exist(self) -> None:
        for f in self.manifest.composite_files:
            self.assertTrue(
                (self.source_root / f).exists(),
                f"composite file missing: {f}",
            )

    def test_all_excluded_files_exist(self) -> None:
        """Excluded files should still exist in the source repo."""
        for f in self.manifest.excluded_files:
            self.assertTrue(
                (self.source_root / f).exists(),
                f"excluded file missing from repo: {f}",
            )


class TestExportedFilesShipped(unittest.TestCase):
    """Files a shipped BUILD exports must themselves be shipped.

    The reverse of :class:`TestManifestFilesExist`: that class checks every
    *listed* path exists; this checks the manifest does not *forget* a file that
    a curated BUILD references. ``tools/lint/BUILD`` exporting
    ``clippy_assert_empty.sh`` without the script being in the manifest is the
    bug this guards — the scaffold built fine until a rust ``.lint`` target tried
    to consume the absent input.
    """

    source_root: Path
    manifest: BootstrapManifest

    @classmethod
    def setUpClass(cls) -> None:
        cls.source_root = _find_source_root()
        cls.manifest = load_manifest(cls.source_root / "tools" / "bootstrap" / "bootstrap_manifest.toml")

    def test_exported_files_are_shipped(self) -> None:
        # The full selection renders every section, so each exports_files block is
        # present and every exported sibling must resolve into the shipped set.
        all_features = set(self.manifest.features)
        resolved = resolve_files(self.manifest, EXPECTED_LANGUAGES, all_features)
        excluded = effective_excluded_files(self.manifest, all_features)
        listed = set(resolved.copy) | set(resolved.composite)
        directories = resolved.directories

        def is_shipped(rel: str) -> bool:
            if rel in listed:
                return True
            # Files under a copied tool directory ride along unless excluded.
            under_dir = any(rel == d or rel.startswith(f"{d}/") for d in directories)
            return under_dir and rel not in excluded

        # Only individually-curated BUILDs can drift: a directory copytree ships
        # its exports alongside it, so the "forgot to list it" gap can't occur.
        build_files = [f for f in (*resolved.composite, *resolved.copy) if Path(f).name in ("BUILD", "BUILD.bazel")]
        for build in build_files:
            content = filter_sections(
                (self.source_root / build).read_text(),
                EXPECTED_LANGUAGES,
                all_features,
                filename=build,
            )
            package = Path(build).parent
            for name in _exported_filenames(content):
                rel = name if package == Path(".") else f"{package}/{name}"
                self.assertTrue(
                    is_shipped(rel),
                    f"{build} exports '{name}' but {rel} is not shipped — add it to the manifest",
                )


class TestMarkerIntegrity(unittest.TestCase):
    """Section markers in composite files must be well-formed."""

    source_root: Path
    manifest: BootstrapManifest

    @classmethod
    def setUpClass(cls) -> None:
        cls.source_root = _find_source_root()
        cls.manifest = load_manifest(cls.source_root / "tools" / "bootstrap" / "bootstrap_manifest.toml")

    def test_composite_files_have_markers(self) -> None:
        """Every composite file contains at least one BEGIN/END pair."""
        for f in self.manifest.composite_files:
            content = (self.source_root / f).read_text()
            begins = _BEGIN_RE.findall(content)
            ends = _END_RE.findall(content)
            self.assertTrue(len(begins) > 0, f"{f} has no BEGIN markers")
            self.assertTrue(len(ends) > 0, f"{f} has no END markers")

    def test_markers_balanced(self) -> None:
        """Every BEGIN has a matching END with the same tag."""
        for f in self.manifest.composite_files:
            content = (self.source_root / f).read_text()
            begins = _BEGIN_RE.findall(content)
            ends = _END_RE.findall(content)
            self.assertEqual(
                sorted(begins),
                sorted(ends),
                f"{f} has unbalanced markers: BEGIN={sorted(begins)} END={sorted(ends)}",
            )

    def test_marker_tags_are_known(self) -> None:
        """Every lang:X tag in markers references a known language or 'core'."""
        known = EXPECTED_LANGUAGES | {"core"}
        for f in self.manifest.composite_files:
            content = (self.source_root / f).read_text()
            for tag in _BEGIN_RE.findall(content):
                if tag == "exclude" or tag.startswith("feature:"):
                    continue
                # tag is "lang:python" or "lang:cpp,java"
                langs = tag.removeprefix("lang:").split(",")
                for lang in langs:
                    self.assertIn(
                        lang,
                        known,
                        f"{f} has unknown tag '{lang}' in marker '{tag}'",
                    )


class TestManifestConsistency(unittest.TestCase):
    """Cross-section consistency checks within the manifest."""

    source_root: Path
    manifest: BootstrapManifest

    @classmethod
    def setUpClass(cls) -> None:
        cls.source_root = _find_source_root()
        cls.manifest = load_manifest(cls.source_root / "tools" / "bootstrap" / "bootstrap_manifest.toml")

    def test_manifest_languages_match_expected(self) -> None:
        """The manifest defines exactly the expected set of languages."""
        self.assertEqual(set(self.manifest.languages.keys()), EXPECTED_LANGUAGES)

    def test_no_duplicate_files_across_sections(self) -> None:
        """No file appears in both core and language-specific sections."""
        core_set = set(self.manifest.core_files)
        for lang, config in self.manifest.languages.items():
            for f in config.files:
                self.assertNotIn(f, core_set, f"{f} is in both core and {lang}")


class TestKeyCompositeFiles(unittest.TestCase):
    """Key composite files contain the expected language sections."""

    source_root: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.source_root = _find_source_root()

    def _read(self, rel_path: str) -> str:
        return (self.source_root / rel_path).read_text()

    def test_module_bazel_has_all_language_includes(self) -> None:
        content = self._read("MODULE.bazel")
        for lang in EXPECTED_LANGUAGES:
            self.assertRegex(
                content,
                rf"BEGIN\s+lang:\S*{lang}",
                f"MODULE.bazel missing section for {lang}",
            )

    def test_format_build_has_all_language_params(self) -> None:
        content = self._read("tools/format/BUILD")
        expected_params = {
            "python": "format:ruff",
            "cpp": "clang-format",
            "rust": "rustfmt",
            "java": "clang_format_wrapper",
            "go": "gofumpt",
        }
        for lang, param in expected_params.items():
            self.assertIn(
                param,
                content,
                f"format/BUILD missing {lang} param '{param}'",
            )

    def test_clang_format_has_tagged_languages(self) -> None:
        content = self._read(".clang-format")
        for lang in ("cpp", "java"):
            self.assertRegex(
                content,
                rf"BEGIN\s+lang:{lang}",
                f".clang-format missing section for {lang}",
            )

    def test_gazelle_directives_filter_per_feature(self) -> None:
        """The shared directive vocabulary (shipped under lint OR publish) keeps
        only the selected feature's directives once filtered.

        Both feature blocks are present in the source, and each survives alone
        when only its feature is selected — so a publish-only fork doesn't carry
        lint_* directives (and vice versa), while neither block is empty.
        """
        content = self._read("tools/gazelle/directives/directives.go")
        # Source carries both feature blocks.
        self.assertRegex(content, r"BEGIN\s+feature:lint")
        self.assertRegex(content, r"BEGIN\s+feature:publish")

        lint_only = filter_sections(content, set(), {"lint"}, filename="directives.go")
        self.assertIn("lint_ignore", lint_only)
        self.assertNotIn("publish_ignore", lint_only)
        # The stripped publish block was the tail of the const(...) group; no
        # blank may dangle before its closing paren (gofmt would flag it).
        self.assertNotIn("\n\n)", lint_only)

        publish_only = filter_sections(content, set(), {"publish"}, filename="directives.go")
        self.assertIn("publish_ignore", publish_only)
        self.assertNotIn("lint_ignore", publish_only)
        self.assertNotIn("\n\n)", publish_only)

    def test_kinds_go_keeps_separator_for_surviving_lang(self) -> None:
        """kinds.go's const(...) has `loadLinters` then a blank, then per-lang
        kind constants. Filtering to one language must keep that blank, else
        gofmt re-aligns the `=` columns of the now-merged group (re-bootstrap
        churn). Regression for the over-eager blank stripping.
        """
        content = self._read("tools/lint/gazelle/kinds.go")
        py_only = filter_sections(content, {"python"}, set(), filename="kinds.go")
        self.assertIn("kindRuffTest", py_only)
        self.assertNotIn("kindClangTidyTest", py_only)
        # loadLinters stays separated from the kind group (no gofmt re-align).
        self.assertRegex(py_only, r'loadLinters = "//tools/lint:linters\.bzl"\n\n\s*kindRuffTest')

    def test_linters_bzl_has_all_language_linters(self) -> None:
        content = self._read("tools/lint/linters.bzl")
        expected = {
            "python": "ruff",
            "cpp": "clang_tidy",
            "rust": "clippy",
            "java": "pmd",
        }
        for lang, linter in expected.items():
            self.assertRegex(
                content,
                rf"BEGIN\s+lang:\S*{lang}",
                f"linters.bzl missing section for {lang}",
            )
            self.assertIn(
                linter,
                content,
                f"linters.bzl missing linter '{linter}' for {lang}",
            )


class TestReadmeTemplate(unittest.TestCase):
    """The generated-README template exists and has well-formed markers."""

    source_root: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.source_root = _find_source_root()

    def _template_path(self) -> Path:
        return self.source_root / "tools" / "bootstrap" / "templates" / "README.md"

    def test_template_exists(self) -> None:
        self.assertTrue(self._template_path().is_file(), "README template missing")

    def test_template_lang_feature_markers_balanced(self) -> None:
        """Every #-style lang/feature BEGIN has a matching END (HTML user-managed
        markers are matched separately and are exempt from this check)."""
        content = self._template_path().read_text()
        begins = _BEGIN_RE.findall(content)
        ends = _END_RE.findall(content)
        self.assertEqual(sorted(begins), sorted(ends), "README template has unbalanced lang/feature markers")

    def test_template_renders_clean_across_selections(self) -> None:
        """filter_sections accepts the template for the extreme selections (no
        nested/mismatched markers) and never leaves a lang/feature marker behind,
        while the user-managed region always survives."""
        content = self._template_path().read_text()
        all_langs = {"python", "cpp", "rust", "java", "go"}
        all_feats = {"lint", "publish"}
        for langs, feats in [(set(), set()), (all_langs, all_feats), ({"cpp"}, set())]:
            rendered = filter_sections(content, langs, feats, filename="README.md")
            self.assertNotRegex(
                rendered,
                r"#\s*---\s*(BEGIN|END)\s+(lang|feature):",
                f"leftover marker for langs={langs} feats={feats}",
            )
            self.assertTrue(has_user_region(rendered), f"user region lost for langs={langs} feats={feats}")


if __name__ == "__main__":
    unittest.main()
