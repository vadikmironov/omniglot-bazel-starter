"""Scaffolding correctness tests — all 31 non-empty language subsets.

For each of the 31 non-empty subsets of {python, cpp, rust, java, go},
scaffolds a repository into a temporary directory and verifies:
  - Core files are always present
  - Language-specific files are present if selected
  - Composite files are present and correctly filtered
  - Excluded files are never present
  - Name substitution is applied
  - No section markers remain in output
  - modules/ and .git/ directories exist
"""

import itertools
import shutil
import tempfile
import unittest
from pathlib import Path

from bootstrap.manifest import (
    BootstrapManifest,
    effective_excluded_files,
    load_manifest,
    resolve_files,
)
from bootstrap.processor import has_user_region
from bootstrap.scaffolder import scaffold_repo

LANGUAGES = ["python", "cpp", "rust", "java", "go"]
TEST_REPO_NAME = "test_repo"
TEST_MODULE_DIR = "modules"

# ── Content markers per language in key composite files ──────────────

# MODULE.bazel: include() lines that reference language segments
MODULE_SEGMENT_MARKERS: dict[str, str] = {
    "python": "python_segment.MODULE.bazel",
    "cpp": "cpp_segment.MODULE.bazel",
    "rust": "rust_segment.MODULE.bazel",
    "java": "java_segment.MODULE.bazel",
    "go": "go_segment.MODULE.bazel",
}

# MODULE.bazel: LLVM segment (shared by cpp and java)
LLVM_SEGMENT_MARKER = "llvm_segment.MODULE.bazel"

# tools/format/BUILD: format_multirun parameters per language
# Note: cpp uses 'cc = "' (the format_multirun cc= parameter) rather than
# "clang-format" because the java sh_binary also references clang-format
# as a data dependency (the LLVM binary is shared).
FORMAT_PARAM_MARKERS: dict[str, str] = {
    "python": "format:ruff",
    "cpp": 'cc = "@llvm_toolchain_llvm',
    "rust": "rustfmt",
    "java": "clang_format_wrapper",
    "go": "gofumpt",
}

# Palantir markers that must be absent from all output
PALANTIR_MARKERS = [
    "PalantirJavaFormatWrapper",
    "palantir-java-format",
]


def _find_source_root() -> Path:
    """Locate the monorepo root by walking up from this test file."""
    # __file__ is at <repo>/tools/bootstrap/tests/test_scaffolder.py
    return Path(__file__).resolve().parents[3]


class TestScaffolder(unittest.TestCase):
    """Base class with shared setup and assertion helpers."""

    source_root: Path
    manifest: BootstrapManifest

    @classmethod
    def setUpClass(cls) -> None:
        cls.source_root = _find_source_root()
        manifest_path = cls.source_root / "tools" / "bootstrap" / "bootstrap_manifest.toml"
        cls.manifest = load_manifest(manifest_path)

    def _scaffold(
        self,
        selected: set[str],
        module_dir: str = TEST_MODULE_DIR,
        features: set[str] | None = None,
    ) -> Path:
        """Scaffold into a temp directory, return path. Registers cleanup."""
        features = features or set()
        tmp = Path(tempfile.mkdtemp(prefix=f"bootstrap_test_{'_'.join(sorted(selected))}_"))
        self.addCleanup(shutil.rmtree, tmp, True)
        resolved = resolve_files(self.manifest, selected, features)
        scaffold_repo(
            source_root=self.source_root,
            target_path=tmp,
            repo_name=TEST_REPO_NAME,
            module_dir=module_dir,
            selected_languages=selected,
            selected_features=features,
            manifest=self.manifest,
            resolved=resolved,
        )
        return tmp

    # ── File presence/absence ────────────────────────────────────────

    def _assert_core_files_present(self, target: Path) -> None:
        """Every core file from the manifest must exist in the target."""
        for f in self.manifest.core_files:
            path = target / f
            self.assertTrue(
                path.exists() or path.is_symlink(),
                f"core file missing: {f}",
            )

    def _assert_language_files(self, target: Path, selected: set[str], features: set[str] | None = None) -> None:
        """Language config files are present iff the language is selected AND the
        file is not feature-conditionally excluded (e.g. .pmd.xml needs lint)."""
        features = features or set()
        excluded = effective_excluded_files(self.manifest, features)
        for lang, config in self.manifest.languages.items():
            for f in config.files:
                path = target / f
                if lang in selected and f not in excluded:
                    self.assertTrue(path.exists(), f"{f} missing (selected {lang})")
                else:
                    self.assertFalse(path.exists(), f"{f} present (unselected {lang} or feature-gated)")

    def _assert_language_directories(self, target: Path, selected: set[str]) -> None:
        """Language tool directories are present if the language is selected.

        Directories that house composite files may be created as a side effect
        of composite file processing; these are excluded from the absence check.
        """
        # Identify language directories that may legitimately be created by an
        # individually-routed file (composite or language file) given the current
        # selection. Always-on composite files count unconditionally; tagged
        # composite/language files count only when one of their languages is
        # selected, so a shard shared across languages (e.g. tools/cpp's LLVM
        # segment, shared by cpp,java) doesn't trip the absence check when only
        # one owner is selected — while an unrelated selection still verifies
        # the directory stays absent.
        all_dirs = [d for cfg in self.manifest.languages.values() for d in cfg.directories]

        def _dirs_for(files: list[str]) -> set[str]:
            return {d for f in files for d in all_dirs if f.startswith(d + "/")}

        housed_dirs: set[str] = _dirs_for(self.manifest.composite_files)
        for tag, files in {**self.manifest.composite_language_files, **self.manifest.language_files}.items():
            if any(t in selected for t in tag.split(",")):
                housed_dirs |= _dirs_for(files)

        for lang, config in self.manifest.languages.items():
            for d in config.directories:
                path = target / d
                if lang in selected:
                    self.assertTrue(path.is_dir(), f"dir {d} missing (selected {lang})")
                elif d not in housed_dirs:
                    self.assertFalse(path.exists(), f"dir {d} present (unselected {lang})")

    def _assert_composite_files_present(self, target: Path) -> None:
        """All composite files must exist in the target."""
        for f in self.manifest.composite_files:
            if f not in self.manifest.excluded_files:
                self.assertTrue((target / f).exists(), f"composite file missing: {f}")

    def _assert_excluded_files_absent(self, target: Path) -> None:
        """Excluded files must never be present."""
        for f in self.manifest.excluded_files:
            self.assertFalse((target / f).exists(), f"excluded file present: {f}")

    def _assert_setup_present(self, target: Path) -> None:
        """The Bazelisk installer (a core directory) ships for every selection."""
        self.assertTrue(
            (target / "tools" / "setup" / "install_bazelisk.sh").exists(),
            "tools/setup/install_bazelisk.sh missing",
        )

    def _assert_conditional_root_configs(self, target: Path, selected: set[str]) -> None:
        """.clang-format ships only for C++/Java; .pre-commit-config.yaml only for Python."""
        clang = target / ".clang-format"
        if {"cpp", "java"} & selected:
            self.assertTrue(clang.exists(), ".clang-format missing with cpp/java")
        else:
            self.assertFalse(clang.exists(), ".clang-format present without cpp/java")

        precommit = target / ".pre-commit-config.yaml"
        if "python" in selected:
            self.assertTrue(precommit.exists(), ".pre-commit-config.yaml missing with python")
        else:
            self.assertFalse(precommit.exists(), ".pre-commit-config.yaml present without python")

    def _assert_readme_generated(self, target: Path, selected: set[str], features: set[str]) -> None:
        """A starter README is generated with a preserved user-managed intro and
        sections gated to the selection."""
        readme = target / "README.md"
        self.assertTrue(readme.exists(), "README.md not generated")
        content = readme.read_text()
        self.assertIn("## Install Bazelisk", content)  # always present
        self.assertNotIn("{{code_dir}}", content, "README code-dir token not substituted")
        self.assertTrue(has_user_region(content), "README.md missing user-managed region")
        # Pre-commit section gated by python; Publishing gated by the publish feature.
        self.assertEqual("## Pre-commit Hooks" in content, "python" in selected)
        self.assertEqual("## Publishing" in content, "publish" in features)

    # ── Content correctness ──────────────────────────────────────────

    def _assert_no_markers(self, target: Path) -> None:
        """No BEGIN/END section marker lines remain in any generated file.

        Covers both ``#`` and ``//`` comment forms and ``lang:`` / ``feature:`` /
        ``exclude`` predicates — the ``//`` + ``feature:`` cases matter for the
        gazelle ``.go`` files, whose markers a directory copy would have leaked.
        The ``user-managed`` region is deliberately not matched (it survives).
        """
        for path in target.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            try:
                content = path.read_text()
            except (UnicodeDecodeError, PermissionError):
                continue
            rel = path.relative_to(target)
            for kind in ("BEGIN", "END"):
                self.assertNotRegex(
                    content,
                    rf"(?:#|//)\s*---\s*{kind}\s+(?:lang:|feature:|exclude)",
                    f"{kind} section marker in {rel}",
                )

    def _assert_name_substitution(self, target: Path) -> None:
        """omniglot-bazel-starter must be replaced with the test repo name."""
        module_bazel = target / "MODULE.bazel"
        content = module_bazel.read_text()
        self.assertNotIn("omniglot-bazel-starter", content, "MODULE.bazel still has omniglot-bazel-starter")
        self.assertIn(TEST_REPO_NAME, content, "MODULE.bazel missing test_repo name")

        bazelignore = target / ".bazelignore"
        if bazelignore.exists():
            content = bazelignore.read_text()
            self.assertNotIn(
                "omniglot-bazel-starter",
                content,
                ".bazelignore still has omniglot-bazel-starter",
            )

    def _assert_module_bazel_content(self, target: Path, selected: set[str]) -> None:
        """MODULE.bazel has include() lines only for selected languages."""
        content = (target / "MODULE.bazel").read_text()
        for lang, marker in MODULE_SEGMENT_MARKERS.items():
            if lang in selected:
                self.assertIn(marker, content, f"MODULE.bazel missing {lang} segment")
            else:
                self.assertNotIn(marker, content, f"MODULE.bazel has unselected {lang} segment")

        # LLVM segment: present when cpp OR java selected
        if "cpp" in selected or "java" in selected:
            self.assertIn(LLVM_SEGMENT_MARKER, content, "MODULE.bazel missing LLVM segment")
        else:
            self.assertNotIn(LLVM_SEGMENT_MARKER, content, "MODULE.bazel has unwanted LLVM segment")

    def _assert_format_build_content(self, target: Path, selected: set[str]) -> None:
        """tools/format/BUILD has format_multirun params only for selected."""
        content = (target / "tools" / "format" / "BUILD").read_text()
        for lang, marker in FORMAT_PARAM_MARKERS.items():
            if lang in selected:
                self.assertIn(marker, content, f"format/BUILD missing {lang} param")
            else:
                self.assertNotIn(marker, content, f"format/BUILD has unselected {lang} param")

    def _assert_palantir_excluded(self, target: Path) -> None:
        """Palantir-related content must be absent from source and config files.

        Lock files (e.g. maven_install.json) are skipped because they are
        generated artifacts that will be re-pinned after scaffolding.
        """
        skip_names = {"maven_install.json"}
        for path in target.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            if path.name in skip_names:
                continue
            try:
                content = path.read_text()
            except (UnicodeDecodeError, PermissionError):
                continue
            rel = path.relative_to(target)
            for marker in PALANTIR_MARKERS:
                self.assertNotIn(marker, content, f"Palantir content in {rel}")

    # ── Structure ────────────────────────────────────────────────────

    def _assert_modules_dir(self, target: Path, module_dir: str = TEST_MODULE_DIR) -> None:
        """Placeholder code directory exists and is empty."""
        modules = target / module_dir
        self.assertTrue(modules.is_dir(), f"{module_dir}/ dir missing")
        contents = list(modules.iterdir())
        self.assertEqual(contents, [], f"{module_dir}/ not empty: {contents}")

    def _assert_git_init(self, target: Path) -> None:
        """.git/ directory exists."""
        self.assertTrue((target / ".git").is_dir(), ".git/ dir missing")

    def _assert_publish_toml_content(self, target: Path, module_dir: str = TEST_MODULE_DIR) -> None:
        """Bootstrapped .publish.toml carries the chosen path_patterns and
        omits the example-app component_sets/components entries."""
        content = (target / ".publish.toml").read_text()
        self.assertIn(f'path_patterns = ["{module_dir}/**"]', content)
        self.assertNotIn("[component_sets.", content)
        self.assertNotIn("[components]", content)
        # No stray //modules/... references from the stripped example apps.
        self.assertNotIn(f"//{module_dir}/", content)

    def _assert_publish_absent(self, target: Path) -> None:
        """Publish feature off: no tools/publish dir, no .publish.toml, no include."""
        self.assertFalse((target / "tools" / "publish").exists(), "tools/publish/ leaked into non-publish scaffold")
        self.assertFalse((target / ".publish.toml").exists(), ".publish.toml leaked into non-publish scaffold")
        module_bazel = (target / "MODULE.bazel").read_text()
        self.assertNotIn("publish_segment.MODULE.bazel", module_bazel)
        # Root BUILD must not reference any publish-only labels or exports.
        self.assertNotIn("tools/publish", (target / "BUILD").read_text(), "tools/publish leaked into root BUILD")
        # .bazelrc must not reference any tools/publish/ paths (e.g. credential_helper),
        # otherwise Bazel warns on every fetch about a missing helper script.
        self.assertNotIn("tools/publish/", (target / ".bazelrc").read_text())
        # user.bazelrc.template would otherwise document publish flags that point at nothing.
        self.assertNotIn(
            "tools/publish",
            (target / "user.bazelrc.template").read_text(),
            "tools/publish leaked into user.bazelrc.template",
        )
        # .ruff.toml per-file-ignores for tools/publish/ would target nonexistent paths.
        ruff_path = target / ".ruff.toml"
        if ruff_path.exists():
            self.assertNotIn("tools/publish/", ruff_path.read_text(), "tools/publish/ leaked into .ruff.toml")

    def _assert_publish_present(self, target: Path) -> None:
        """Publish feature on: tools/publish dir, .publish.toml, include line present."""
        self.assertTrue((target / "tools" / "publish").is_dir(), "tools/publish/ missing from publish scaffold")
        self.assertTrue((target / ".publish.toml").exists(), ".publish.toml missing from publish scaffold")
        module_bazel = (target / "MODULE.bazel").read_text()
        self.assertIn("publish_segment.MODULE.bazel", module_bazel)
        self.assertIn('name = "publish_gen"', (target / "BUILD").read_text())

    def _assert_lint_absent(self, target: Path) -> None:
        """Lint feature off: no tools/lint/gazelle dir, no lint_gen rule."""
        self.assertFalse(
            (target / "tools" / "lint" / "gazelle").exists(), "tools/lint/gazelle/ leaked into non-lint scaffold"
        )
        self.assertNotIn('name = "lint_gen"', (target / "BUILD").read_text())

    def _assert_lint_present(self, target: Path) -> None:
        """Lint feature on: tools/lint/gazelle dir, lint_gen rule present."""
        self.assertTrue(
            (target / "tools" / "lint" / "gazelle").is_dir(), "tools/lint/gazelle/ missing from lint scaffold"
        )
        self.assertIn('name = "lint_gen"', (target / "BUILD").read_text())

    def _assert_lint_off_clean(self, target: Path, selected: set[str]) -> None:
        """Lint feature off: no analyzer aspects, deps, or wiring leak in.

        Per-language config files (.pmd.xml, .nogo_config.json, …) are covered by
        _assert_language_files; this focuses on the composite-file gating.
        """
        # Linter aspect definitions/binaries are lint-owned — never present otherwise.
        self.assertFalse((target / "tools" / "lint" / "linters.bzl").exists(), "linters.bzl leaked without lint")
        self.assertFalse((target / "tools" / "lint" / "BUILD").exists(), "tools/lint/BUILD leaked without lint")
        # No nogo rule in root BUILD.
        self.assertNotIn("nogo", (target / "BUILD").read_text(), "nogo rule leaked into root BUILD")
        if "python" in selected:
            req = (target / "tools" / "python" / "requirements.in").read_text()
            for tool in ("ruff", "bandit", "ty"):
                self.assertNotIn(tool, req, f"{tool} leaked into requirements.in without lint")
            self.assertIn("pre-commit", req, "pre-commit should remain (not lint-only)")
            ruff = (target / ".ruff.toml").read_text()
            self.assertIn("line-length", ruff, ".ruff.toml should keep its formatter config")
            self.assertNotIn("[lint]", ruff, ".ruff.toml [lint] block leaked without lint")
        if "java" in selected:
            seg = (target / "tools" / "java" / "java_segment.MODULE.bazel").read_text()
            self.assertNotIn("pmd-core", seg, "PMD dep leaked without lint")
            self.assertNotIn("spotbugs", seg, "SpotBugs dep leaked without lint")
            self.assertIn("log4j-core", seg, "log4j (general logging dep) should remain")
        if "go" in selected:
            self.assertNotIn(
                "go_sdk.nogo",
                (target / "tools" / "go" / "go_segment.MODULE.bazel").read_text(),
                "nogo registration leaked without lint",
            )

    # ── Combined assertion runner ────────────────────────────────────

    def _assert_scaffold_correct(self, selected: set[str]) -> None:
        """Run all assertions for a given language subset (no features)."""
        target = self._scaffold(selected)

        # File presence
        self._assert_core_files_present(target)
        self._assert_language_files(target, selected)
        self._assert_language_directories(target, selected)
        self._assert_composite_files_present(target)
        self._assert_excluded_files_absent(target)
        self._assert_setup_present(target)
        self._assert_conditional_root_configs(target, selected)
        self._assert_readme_generated(target, selected, set())

        # Content correctness
        self._assert_no_markers(target)
        self._assert_name_substitution(target)
        self._assert_module_bazel_content(target, selected)
        self._assert_format_build_content(target, selected)
        self._assert_palantir_excluded(target)
        # known-first-party = ["bootstrap"] is bootstrap-tool-specific; must never ship.
        # Match the quoted package token so the bare word "bootstrap" in the
        # user-managed seed comment ("Preserved across re-bootstrap.") is not a
        # false positive.
        if "python" in selected:
            self.assertNotIn(
                '"bootstrap"',
                (target / ".ruff.toml").read_text(),
                ".ruff.toml leaked bootstrap-tool first-party",
            )
            # questionary is the bootstrap CLI's own dep; scaffolded repos shouldn't pull it.
            self.assertNotIn(
                "questionary",
                (target / "tools" / "python" / "requirements.in").read_text(),
                "requirements.in leaked bootstrap-tool dep questionary",
            )
        # Publish + lint features are opt-in; default subsets must NOT ship them.
        self._assert_publish_absent(target)
        self._assert_lint_absent(target)
        self._assert_lint_off_clean(target, selected)

        # Structure
        self._assert_modules_dir(target)
        self._assert_git_init(target)

    def test_module_dir_override(self) -> None:
        """A non-default *module_dir* renames the placeholder and rewrites
        the path_patterns convention in the bootstrapped .publish.toml."""
        target = self._scaffold({"python", "go"}, module_dir="services", features={"publish"})
        self._assert_modules_dir(target, module_dir="services")
        self.assertFalse((target / "modules").exists(), "default modules/ dir should not be created")
        self._assert_publish_toml_content(target, module_dir="services")

    def test_module_dir_override_rewrites_bazelrc_analyzer_scope(self) -> None:
        """A non-default *module_dir* is tracked in .bazelrc's gcc_analyzer
        per_file_copt, so -fanalyzer still scopes to first-party C++. The line
        is template content (not a user-managed region), so a literal `modules/`
        could not be hand-fixed permanently — re-bootstrap would clobber it."""
        target = self._scaffold({"cpp"}, module_dir="services")
        bazelrc = (target / ".bazelrc").read_text()
        self.assertIn("--per_file_copt=services/", bazelrc)
        self.assertNotIn("--per_file_copt=modules/", bazelrc)

    def test_publish_feature_with_go(self) -> None:
        """Publish + Go selected: full publish stack ships."""
        target = self._scaffold({"go"}, features={"publish"})
        self._assert_publish_present(target)
        self._assert_publish_toml_content(target)
        # tools/publish/gazelle/ should ship when Go is selected.
        self.assertTrue((target / "tools" / "publish" / "gazelle").is_dir())

    def test_publish_feature_auto_promotes_go(self) -> None:
        """Selecting publish without Go pulls Go in via the feature's requires."""
        # The CLI does the promotion, but resolve_files honors it directly too.
        target = self._scaffold({"python"} | {"go"}, features={"publish"})
        self._assert_publish_present(target)
        # Go segment is present because publish requires go.
        module_bazel = (target / "MODULE.bazel").read_text()
        self.assertIn("go_segment.MODULE.bazel", module_bazel)

    def test_lint_feature_with_go(self) -> None:
        """Lint feature selected with Go: gazelle subdir + lint_gen rule ship."""
        target = self._scaffold({"go"}, features={"lint"})
        self._assert_lint_present(target)

    def test_lint_feature_without_go_in_selection(self) -> None:
        """Selecting lint without Go pulls Go in via the feature's requires."""
        target = self._scaffold({"python"} | {"go"}, features={"lint"})
        self._assert_lint_present(target)
        module_bazel = (target / "MODULE.bazel").read_text()
        self.assertIn("go_segment.MODULE.bazel", module_bazel)

    def test_publish_does_not_imply_lint(self) -> None:
        """Selecting only publish must not ship the lint gazelle subdir."""
        target = self._scaffold({"go"}, features={"publish"})
        self._assert_publish_present(target)
        self._assert_lint_absent(target)
        self._assert_lint_off_clean(target, {"go"})

    def test_lint_feature_full_stack(self) -> None:
        """Lint on: analyzer aspects, deps, configs, and gazelle all ship."""
        target = self._scaffold({"python", "java", "go"}, features={"lint"})
        self._assert_lint_present(target)
        self.assertTrue((target / "tools" / "lint" / "linters.bzl").exists())
        self.assertTrue((target / "tools" / "lint" / "BUILD").exists())
        # Python analyzers: deps, aspect wiring, configs.
        req = (target / "tools" / "python" / "requirements.in").read_text()
        for tool in ("ruff", "bandit", "ty"):
            self.assertIn(tool, req)
        self.assertTrue((target / "ty.toml").exists())
        self.assertIn("[lint]", (target / ".ruff.toml").read_text())
        # Java analyzers: deps + rulesets.
        seg = (target / "tools" / "java" / "java_segment.MODULE.bazel").read_text()
        self.assertIn("pmd-core", seg)
        self.assertIn("spotbugs", seg)
        self.assertTrue((target / ".pmd.xml").exists())
        self.assertTrue((target / ".spotbugs-exclude.xml").exists())
        # Go analyzer: nogo registration + rule + config.
        self.assertIn("go_sdk.nogo", (target / "tools" / "go" / "go_segment.MODULE.bazel").read_text())
        self.assertIn("nogo", (target / "BUILD").read_text())
        self.assertTrue((target / ".nogo_config.json").exists())

    def test_profiling_feature_on(self) -> None:
        """Profiling on: the runner ships and every wiring block lands."""
        target = self._scaffold({"rust", "go", "python"}, features={"profiling"})
        self.assertTrue((target / "tools" / "profile" / "BUILD").exists())
        self.assertTrue((target / "tools" / "profile" / "src" / "profiling" / "cli.py").exists())
        self.assertTrue((target / "tools" / "profile" / "gazelle" / "rust.go").exists())
        # python is in the base selection, so its generator ships too.
        self.assertTrue((target / "tools" / "profile" / "gazelle" / "python.go").exists())
        # cpp/java are not selected: their generators must be pruned from
        # the tools/profile directory copy, not shipped raw with markers.
        self.assertFalse((target / "tools" / "profile" / "gazelle" / "cpp.go").exists())
        self.assertFalse((target / "tools" / "profile" / "gazelle" / "java.go").exists())
        self.assertIn("profile_gen", (target / "BUILD").read_text())
        self.assertIn("build:profile", (target / ".bazelrc").read_text())
        self.assertIn("inferno", (target / "tools" / "rust" / "Cargo.toml").read_text())
        self.assertIn("gen_binaries", (target / "tools" / "rust" / "rust_segment.MODULE.bazel").read_text())
        self.assertIn("pprofutils", (target / "go.mod").read_text())
        self.assertIn(
            "com_github_felixge_pprofutils_v2",
            (target / "tools" / "go" / "go_segment.MODULE.bazel").read_text(),
        )
        self.assertIn("/profile-out/", (target / ".gitignore").read_text())
        self.assertIn("## Profiling", (target / "README.md").read_text())
        self._assert_no_markers(target)

    def test_profiling_feature_with_cpp(self) -> None:
        """Profiling + cpp: the C++ capture wiring ships marker-filtered."""
        target = self._scaffold({"rust", "go", "python", "cpp"}, features={"profiling"})
        self.assertTrue((target / "tools" / "profile" / "gazelle" / "cpp.go").exists())
        self.assertIn("google_benchmark", (target / ".bazelrc").read_text())
        self.assertIn("gperftools", (target / "tools" / "cpp" / "cpp_3rd_party_dependencies.MODULE.bazel").read_text())
        self.assertIn("tool github.com/google/pprof", (target / "go.mod").read_text())
        self.assertIn(
            "com_github_google_pprof",
            (target / "tools" / "go" / "go_segment.MODULE.bazel").read_text(),
        )
        engine = (target / "tools" / "profile" / "src" / "profiling" / "engine.py").read_text()
        self.assertIn("google_benchmark", engine)
        self.assertIn("PROFILE_PPROF", (target / "tools" / "profile" / "BUILD").read_text())
        self._assert_no_markers(target)

    def test_profiling_feature_with_java(self) -> None:
        """Profiling + java: the Java capture wiring ships marker-filtered."""
        target = self._scaffold({"rust", "go", "python", "java"}, features={"profiling"})
        self.assertTrue((target / "tools" / "profile" / "gazelle" / "java.go").exists())
        self.assertIn("jmh", (target / "tools" / "java" / "java_segment.MODULE.bazel").read_text())
        profile_build = (target / "tools" / "profile" / "BUILD").read_text()
        self.assertIn("jfrconv", profile_build)
        self.assertIn("jmh_annprocess", profile_build)
        engine = (target / "tools" / "profile" / "src" / "profiling" / "engine.py").read_text()
        self.assertIn("_jmh_args", engine)
        self._assert_no_markers(target)

    def test_profiling_feature_off(self) -> None:
        """Profiling off: no tools/profile dir and no wiring leaks anywhere."""
        target = self._scaffold({"rust", "go", "python"})
        self.assertFalse((target / "tools" / "profile").exists())
        self.assertNotIn("build:profile", (target / ".bazelrc").read_text())
        self.assertNotIn("inferno", (target / "tools" / "rust" / "Cargo.toml").read_text())
        self.assertNotIn("gen_binaries", (target / "tools" / "rust" / "rust_segment.MODULE.bazel").read_text())
        self.assertNotIn("pprofutils", (target / "go.mod").read_text())
        self.assertNotIn("pprofutils", (target / "tools" / "go" / "go_segment.MODULE.bazel").read_text())
        self.assertNotIn("/profile-out/", (target / ".gitignore").read_text())
        self.assertNotIn("## Profiling", (target / "README.md").read_text())

    def test_lint_gazelle_section_filtered(self) -> None:
        """The gazelle extension is section-filtered, not raw-copied.

        Regression for the directory-copy leak: with rust+go+lint, only the
        rust generator ships, the multi-language files have their cpp/java/python
        blocks (and all markers) stripped, and BUILD srcs lists only present
        files. Other languages' generators are absent (not emptied stubs).
        """
        target = self._scaffold({"rust", "go"}, features={"lint"})
        gazelle = target / "tools" / "lint" / "gazelle"
        self.assertTrue(gazelle.is_dir())

        # Single-language generators: only the selected language's file ships.
        self.assertTrue((gazelle / "rust.go").exists(), "rust.go missing for rust+lint")
        for absent in ("cpp.go", "java.go", "python.go"):
            self.assertFalse((gazelle / absent).exists(), f"{absent} leaked for a non-{absent[:-3]} repo")
        # Marker-free contract + multi-language files always ship with lint.
        for present in ("lang.go", "kinds.go", "generate.go", "BUILD"):
            self.assertTrue((gazelle / present).exists(), f"{present} missing from lint scaffold")

        # No section markers survive in any gazelle file (covers // + feature:).
        self._assert_no_markers(target)

        # BUILD srcs must reference only the files that shipped. Match the quoted
        # srcs form ("rust.go") so the descriptive header comment — which lists
        # every generator by name — doesn't give a false positive.
        build = (gazelle / "BUILD").read_text()
        self.assertIn('"rust.go"', build)
        for absent in ("cpp.go", "java.go", "python.go"):
            self.assertNotIn(f'"{absent}"', build, f"{absent} still listed in gazelle BUILD srcs")

    def test_go_import_paths_substituted(self) -> None:
        """Go sources get the module-name substitution like BUILD/go.mod.

        Regression for the strict-deps break: the shared vocab imports
        //tools/gazelle/directives by its full module path, so if .go files are
        skipped by substitution the import keeps the old `omniglot-bazel-starter`
        prefix while its BUILD importpath becomes the new repo name — and the dep
        no longer resolves. Both must carry TEST_REPO_NAME and neither the source.
        """
        target = self._scaffold({"go"}, features={"lint", "publish"})
        vocab_go = (target / "tools" / "gazelle" / "vocab" / "vocab.go").read_text()
        self.assertIn(f"{TEST_REPO_NAME}/tools/gazelle/directives", vocab_go)
        self.assertNotIn("omniglot-bazel-starter", vocab_go)
        # The importpath in BUILD must match the now-substituted import.
        directives_build = (target / "tools" / "gazelle" / "directives" / "BUILD").read_text()
        self.assertIn(f'importpath = "{TEST_REPO_NAME}/tools/gazelle/directives"', directives_build)
        # The lint generator that imports it must agree too.
        lang_go = (target / "tools" / "lint" / "gazelle" / "lang.go").read_text()
        self.assertIn(f"{TEST_REPO_NAME}/tools/gazelle/directives", lang_go)
        self.assertNotIn("omniglot-bazel-starter", lang_go)

    def test_remote_cache_feature_gating(self) -> None:
        """remote_cache toggles the BuildBuddy wiring in .bazelrc, the
        user.bazelrc.template API-key block, and the README section."""
        on = self._scaffold({"go"}, features={"remote_cache"})
        self.assertIn("build:remote-cache --remote_cache=", (on / ".bazelrc").read_text())
        self.assertIn("x-buildbuddy-api-key", (on / "user.bazelrc.template").read_text())
        self.assertIn("## Remote Cache (BuildBuddy)", (on / "README.md").read_text())
        # try-import of user.bazelrc is language-core, not cache-gated — always present.
        self.assertIn("try-import %workspace%/user.bazelrc", (on / ".bazelrc").read_text())

        off = self._scaffold({"go"})
        bazelrc = (off / ".bazelrc").read_text()
        self.assertNotIn("build:remote-cache", bazelrc, "remote-cache config leaked without feature")
        self.assertNotIn("build:ci", bazelrc, "ci config leaked without remote_cache feature")
        self.assertIn("try-import %workspace%/user.bazelrc", bazelrc, "user.bazelrc try-import should remain")
        self.assertNotIn("x-buildbuddy-api-key", (off / "user.bazelrc.template").read_text())
        self.assertNotIn("## Remote Cache (BuildBuddy)", (off / "README.md").read_text())

    def test_ruff_publish_ignores_need_lint_and_publish(self) -> None:
        """The .ruff.toml publish per-file-ignores require lint AND publish (AND tag)."""
        both = self._scaffold({"python", "go"}, features={"lint", "publish"})
        self.assertIn("tools/publish/src/mint", (both / ".ruff.toml").read_text())
        lint_only = self._scaffold({"python", "go"}, features={"lint"})
        self.assertNotIn("tools/publish", (lint_only / ".ruff.toml").read_text())

    def test_publish_without_lint_gates_ruff_test(self) -> None:
        """publish on / lint off: tools/publish/BUILD ships but its ruff_test is gated."""
        target = self._scaffold({"go"}, features={"publish"})
        build = (target / "tools" / "publish" / "BUILD").read_text()
        self.assertNotIn("ruff_test", build)
        self.assertNotIn("linters.bzl", build)

    def test_readme_sections_gated_by_features(self) -> None:
        """README Publishing/lint sections track the selected features; the Go
        lock-refresh command appears, the Python one does not."""
        target = self._scaffold({"python", "go"}, features={"publish"})
        content = (target / "README.md").read_text()
        self.assertIn("## Pre-commit Hooks", content)  # python selected
        self.assertIn("## Publishing", content)  # publish feature on
        self.assertNotIn("test_tag_filters=lint", content)  # lint feature off
        # Per-language lock-refresh lines are gated by language.
        self.assertIn("generate_requirements_lock.update", content)  # python
        self.assertIn("@rules_go//go -- mod tidy", content)  # go
        self.assertNotIn("CARGO_BAZEL_REPIN", content)  # rust not selected

        lint_target = self._scaffold({"go"}, features={"lint"})
        self.assertIn("test_tag_filters=lint", (lint_target / "README.md").read_text())

    def test_readme_user_region_preserved_on_rescaffold(self) -> None:
        """Re-scaffolding refreshes the README baseline but carries the user's
        edited intro region forward via the user-managed splice."""
        target = self._scaffold({"go"})
        readme = target / "README.md"
        readme.write_text(
            "# placeholder\n\n<!-- --- BEGIN user-managed --- -->\nMY CUSTOM INTRO\n<!-- --- END user-managed --- -->\n"
        )
        resolved = resolve_files(self.manifest, {"go"})
        scaffold_repo(
            source_root=self.source_root,
            target_path=target,
            repo_name=TEST_REPO_NAME,
            module_dir=TEST_MODULE_DIR,
            selected_languages={"go"},
            selected_features=set(),
            manifest=self.manifest,
            resolved=resolved,
        )
        content = readme.read_text()
        self.assertIn("MY CUSTOM INTRO", content)  # user intro preserved
        self.assertNotIn("Describe your project here", content)  # seed replaced
        self.assertIn("## Install Bazelisk", content)  # baseline refreshed

    def test_custom_toolchains_gating(self) -> None:
        """custom_toolchains ON ships each language's toolchain dir, its host/local
        registration, and the README section; OFF drops them while keeping every
        language's hermetic default."""
        langs = {"python", "cpp", "java", "go"}
        on = self._scaffold(langs, features={"custom_toolchains"})
        off = self._scaffold(langs)

        for d in ("tools/cpp/toolchains", "tools/go/toolchains", "tools/java/toolchains"):
            self.assertTrue((on / d).is_dir(), f"{d} missing with custom_toolchains")
            self.assertFalse((off / d).exists(), f"{d} present without custom_toolchains")

        # cpp_segment: rules_cc dep always; host register block gated.
        cpp_on = (on / "tools" / "cpp" / "cpp_segment.MODULE.bazel").read_text()
        cpp_off = (off / "tools" / "cpp" / "cpp_segment.MODULE.bazel").read_text()
        self.assertIn("rules_cc", cpp_on)
        self.assertIn("rules_cc", cpp_off)
        self.assertIn("host_gcc_cc_toolchain", cpp_on)
        self.assertNotIn("host_gcc_cc_toolchain", cpp_off)

        # java_segment: rules_jvm_external always; ALL Corretto (local + remote) gated.
        java_on = (on / "tools" / "java" / "java_segment.MODULE.bazel").read_text()
        java_off = (off / "tools" / "java" / "java_segment.MODULE.bazel").read_text()
        self.assertIn("rules_jvm_external", java_off)
        for needle in ("local_corretto_toolchains", "remote_corretto_toolchains", "local_host_jdk_17_toolchain"):
            self.assertIn(needle, java_on)
            self.assertNotIn(needle, java_off)

        # go_segment: local SDK gated.
        self.assertIn("go_local_sdk", (on / "tools" / "go" / "go_segment.MODULE.bazel").read_text())
        self.assertNotIn("go_local_sdk", (off / "tools" / "go" / "go_segment.MODULE.bazel").read_text())

        # .bazelrc: custom configs gated; hermetic default JDK stays either way.
        rc_on = (on / ".bazelrc").read_text()
        rc_off = (off / ".bazelrc").read_text()
        for cfg in ("gcc_host", "clang_host", "python3_13_host", "go_local_sdk", "local_corretto", "remote_corretto"):
            self.assertIn(cfg, rc_on, f"{cfg} missing with custom_toolchains")
            self.assertNotIn(cfg, rc_off, f"{cfg} present without custom_toolchains")
        self.assertIn("remotejdk_17", rc_on)
        self.assertIn("remotejdk_17", rc_off)

        # README Custom Toolchains section gated by the feature.
        self.assertIn("## Custom Toolchains", (on / "README.md").read_text())
        self.assertNotIn("## Custom Toolchains", (off / "README.md").read_text())

    def test_custom_toolchains_noop_for_rust(self) -> None:
        """Selecting custom_toolchains with only Rust is a clean no-op: no toolchain
        dirs, no README section (rules_rust has no local toolchain)."""
        target = self._scaffold({"rust"}, features={"custom_toolchains"})
        self.assertFalse((target / "tools" / "cpp" / "toolchains").exists())
        self.assertNotIn("## Custom Toolchains", (target / "README.md").read_text())


# ── Dynamic test generation for all 31 non-empty subsets ─────────────


def _make_test(combo: tuple[str, ...]):  # type: ignore[type-arg]
    """Create a test method for the given language combination."""

    def test_method(self: TestScaffolder) -> None:
        self._assert_scaffold_correct(set(combo))

    test_method.__doc__ = f"Scaffold with {{{', '.join(combo)}}}"
    return test_method


for _size in range(1, len(LANGUAGES) + 1):
    for _combo in itertools.combinations(LANGUAGES, _size):
        _name = "test_scaffold_" + "_".join(_combo)
        setattr(TestScaffolder, _name, _make_test(_combo))


if __name__ == "__main__":
    unittest.main()
