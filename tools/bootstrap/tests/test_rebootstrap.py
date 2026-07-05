"""Re-bootstrap behavior — user-managed regions survive a second scaffold.

Scaffolds into a temp dir, simulates a user editing the user-managed region
of a managed dependency file, then scaffolds again into the same dir and
verifies the edit survived while the starter baseline stayed intact.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from bootstrap.detect import detect_repo
from bootstrap.manifest import (
    BOOTSTRAP_MARKER_FILE,
    BootstrapManifest,
    compute_prune_set,
    load_manifest,
    read_bootstrap_marker,
    resolve_files,
    write_bootstrap_marker,
)
from bootstrap.processor import has_user_region
from bootstrap.scaffolder import feature_remover_commands, prune_paths, scaffold_repo

TEST_REPO_NAME = "rebootstrap_test"

# Source-repo paths of the managed dependency files (relative to repo root).
MANAGED_SOURCE_FILES = [
    ".gitignore",
    "tools/python/requirements.in",
    "tools/rust/Cargo.toml",
    "tools/cpp/cpp_3rd_party_dependencies.MODULE.bazel",
    "tools/java/java_segment.MODULE.bazel",
]


def _find_source_root() -> Path:
    return Path(__file__).resolve().parents[3]


class _ScaffoldHarness(unittest.TestCase):
    """Shared setup + helpers for scaffolding into throwaway temp dirs."""

    source_root: Path
    manifest: BootstrapManifest

    @classmethod
    def setUpClass(cls) -> None:
        cls.source_root = _find_source_root()
        cls.manifest = load_manifest(cls.source_root / "tools" / "bootstrap" / "bootstrap_manifest.toml")

    def _scaffold_into(
        self,
        target: Path,
        selected: set[str],
        features: set[str] | None = None,
        module_dir: str = "modules",
    ) -> None:
        features = features or set()
        resolved = resolve_files(self.manifest, selected, features)
        scaffold_repo(
            source_root=self.source_root,
            target_path=target,
            repo_name=TEST_REPO_NAME,
            module_dir=module_dir,
            selected_languages=selected,
            selected_features=features,
            manifest=self.manifest,
            resolved=resolved,
        )

    def _fresh_target(self) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="rebootstrap_"))
        self.addCleanup(shutil.rmtree, tmp, True)
        return tmp


class TestRebootstrap(_ScaffoldHarness):
    """User-managed regions survive a second scaffold."""

    def test_managed_source_files_have_user_region(self) -> None:
        """Each managed source file declares exactly one user-managed region."""
        for rel in MANAGED_SOURCE_FILES:
            content = (self.source_root / rel).read_text()
            self.assertTrue(has_user_region(content), f"{rel} missing a well-formed user-managed region")

    def test_requirements_user_edit_survives(self) -> None:
        target = self._fresh_target()
        self._scaffold_into(target, {"python"})
        req = target / "tools" / "python" / "requirements.in"

        # User appends a dependency inside the user-managed region.
        edited = req.read_text().replace(
            "# --- END user-managed ---",
            "flask==3.0.0\n# --- END user-managed ---",
            1,
        )
        req.write_text(edited)

        self._scaffold_into(target, {"python"})  # re-bootstrap
        result = req.read_text()
        self.assertIn("flask==3.0.0", result, "user dependency lost on re-bootstrap")
        # pre-commit is an unconditional starter dep (ruff/ty are lint-gated now);
        # its presence proves the baseline was refreshed alongside the user region.
        self.assertIn("pre-commit", result, "starter baseline lost on re-bootstrap")

    def test_unedited_rebootstrap_is_idempotent(self) -> None:
        target = self._fresh_target()
        self._scaffold_into(target, {"python", "rust"})
        req = target / "tools" / "python" / "requirements.in"
        cargo = target / "tools" / "rust" / "Cargo.toml"
        before = (req.read_text(), cargo.read_text())

        self._scaffold_into(target, {"python", "rust"})  # re-bootstrap, no edits
        after = (req.read_text(), cargo.read_text())
        self.assertEqual(before, after, "re-bootstrap with no edits changed managed files")

    def test_cargo_user_edit_stays_under_dependencies(self) -> None:
        target = self._fresh_target()
        self._scaffold_into(target, {"rust"})
        cargo = target / "tools" / "rust" / "Cargo.toml"

        edited = cargo.read_text().replace(
            "# --- END user-managed ---",
            'serde = { version = "1" }\n# --- END user-managed ---',
            1,
        )
        cargo.write_text(edited)

        self._scaffold_into(target, {"rust"})  # re-bootstrap
        result = cargo.read_text()
        self.assertIn("serde", result, "user crate lost on re-bootstrap")
        # The user crate must remain a member of [dependencies].
        self.assertGreater(
            result.index("serde"),
            result.index("[dependencies]"),
            "user crate escaped [dependencies]",
        )

    def test_gitignore_user_edit_survives(self) -> None:
        target = self._fresh_target()
        self._scaffold_into(target, {"python"})
        gi = target / ".gitignore"

        # User appends a project-specific ignore inside the user-managed region.
        edited = gi.read_text().replace(
            "# --- END user-managed ---",
            "secrets/\n# --- END user-managed ---",
            1,
        )
        gi.write_text(edited)

        self._scaffold_into(target, {"python"})  # re-bootstrap
        result = gi.read_text()
        self.assertIn("secrets/", result, "user gitignore entry lost on re-bootstrap")
        # Bazel core ignores prove the baseline was refreshed alongside the user region.
        self.assertIn("/bazel-*", result, "starter baseline lost on re-bootstrap")

    def test_gomod_is_not_managed(self) -> None:
        """go.mod carries no user-managed region — it is import-driven (tidy)."""
        target = self._fresh_target()
        self._scaffold_into(target, {"go"})
        gomod = (target / "go.mod").read_text()
        self.assertFalse(has_user_region(gomod), "go.mod should not be a managed file")


class TestDetect(_ScaffoldHarness):
    """detect_repo reads a scaffolded repo's name, languages, and features."""

    def test_detects_name_languages_no_features(self) -> None:
        target = self._fresh_target()
        self._scaffold_into(target, {"python", "rust"})
        detected = detect_repo(target, self.manifest)
        if detected is None:
            self.fail("expected detect_repo to recognize the scaffolded repo")
        self.assertEqual(detected.name, TEST_REPO_NAME)
        self.assertEqual(detected.languages, {"python", "rust"})
        self.assertEqual(detected.features, set())

    def test_detects_feature_and_promoted_language(self) -> None:
        # publish requires go, so scaffolding it promotes go into the repo.
        target = self._fresh_target()
        self._scaffold_into(target, {"python", "go"}, features={"publish"})
        detected = detect_repo(target, self.manifest)
        if detected is None:
            self.fail("expected detect_repo to recognize the scaffolded repo")
        self.assertIn("go", detected.languages)
        self.assertEqual(detected.features, {"publish"})

    def test_detects_custom_module_dir(self) -> None:
        target = self._fresh_target()
        self._scaffold_into(target, {"python"}, module_dir="services")
        detected = detect_repo(target, self.manifest)
        if detected is None:
            self.fail("expected detect_repo to recognize the scaffolded repo")
        self.assertEqual(detected.module_dir, "services")

    def test_returns_none_for_non_repo(self) -> None:
        self.assertIsNone(detect_repo(self._fresh_target(), self.manifest))

    def test_returns_none_without_marker(self) -> None:
        # Detection is marker-driven: a repo with MODULE.bazel but no marker
        # (e.g. scaffolded before the marker existed) is treated as un-detected,
        # so the CLI asks the user rather than guessing from the filesystem.
        target = self._fresh_target()
        self._scaffold_into(target, {"python", "rust"})
        (target / BOOTSTRAP_MARKER_FILE).unlink()
        self.assertIsNone(detect_repo(target, self.manifest))

    def test_marker_is_authoritative_over_filesystem(self) -> None:
        # The marker — not the on-disk tool dirs — is the source of truth.
        target = self._fresh_target()
        self._scaffold_into(target, {"python"})  # filesystem has only python
        write_bootstrap_marker(target, "custom", {"python", "go"}, {"lint"})
        detected = detect_repo(target, self.manifest)
        if detected is None:
            self.fail("expected detect_repo to recognize the scaffolded repo")
        self.assertEqual(detected.languages, {"python", "go"})
        self.assertEqual(detected.features, {"lint"})
        self.assertEqual(detected.module_dir, "custom")


class TestComputePruneSet(_ScaffoldHarness):
    """compute_prune_set — pure diff of old vs new shipped paths (no filesystem)."""

    def test_no_change_is_empty(self) -> None:
        prune = compute_prune_set(self.manifest, {"python", "rust"}, set(), {"python", "rust"}, set())
        self.assertEqual(prune, set())

    def test_remove_all_features_lists_owned_and_gated(self) -> None:
        prune = compute_prune_set(
            self.manifest,
            old_languages={"python", "go"},
            old_features={"publish", "lint"},
            new_languages={"python", "go"},
            new_features=set(),
        )
        expected = {
            # publish-owned (directory + composite files)
            "tools/publish",
            ".publish.toml",
            "tools/publish/BUILD",
            # lint-owned: the gazelle extension is enumerated file-by-file (no
            # verbatim directory), so each composite file is owned individually.
            "tools/lint/linters.bzl",
            "tools/lint/BUILD",
            "tools/lint/gazelle/lang.go",
            "tools/lint/gazelle/BUILD",
            "tools/lint/gazelle/kinds.go",
            "tools/lint/gazelle/generate.go",
            # Single-language generator: only python.go, since the old selection
            # had python (not cpp/rust/java) among its languages.
            "tools/lint/gazelle/python.go",
            # Shared gazelle vocabulary — owned by lint OR publish, so dropping
            # BOTH (as here) prunes it; dropping only one would keep it.
            "tools/gazelle/directives/directives.go",
            "tools/gazelle/directives/BUILD",
            "tools/gazelle/vocab/vocab.go",
            "tools/gazelle/vocab/BUILD",
            # when_feature_absent.lint configs (gated term) — independent of language
            ".nogo_config.json",
            ".pmd.xml",
            ".spotbugs-exclude.xml",
        }
        self.assertEqual(prune, expected)

    def test_remove_language_prunes_only_its_artifacts(self) -> None:
        prune = compute_prune_set(self.manifest, {"python", "rust"}, set(), {"python"}, set())
        # Rust-owned dir, composite, and root config files are pruned.
        self.assertIn("tools/rust", prune)
        self.assertIn("tools/rust/Cargo.toml", prune)
        self.assertIn(".rustfmt.toml", prune)
        self.assertIn(".clippy.toml", prune)
        # Nothing Python-owned is touched.
        self.assertFalse(any(p.startswith("tools/python") for p in prune), prune)


class TestPrunePaths(_ScaffoldHarness):
    """prune_paths — filesystem deletion, tolerant of overlap and missing paths."""

    def test_deletes_files_and_dirs_tolerating_overlap(self) -> None:
        target = self._fresh_target()
        (target / "tools" / "rust").mkdir(parents=True)
        (target / "tools" / "rust" / "Cargo.toml").write_text("x")
        (target / ".rustfmt.toml").write_text("y")
        # Parent + child overlap, plus a non-existent path — all handled.
        removed = prune_paths(target, ["tools/rust/Cargo.toml", "tools/rust", ".rustfmt.toml", "does/not/exist"])
        self.assertFalse((target / "tools" / "rust").exists())
        self.assertFalse((target / ".rustfmt.toml").exists())
        # Child removed as a no-op once its parent dir was deleted (sorted order).
        self.assertNotIn("tools/rust/Cargo.toml", removed)
        self.assertIn("tools/rust", removed)
        self.assertIn(".rustfmt.toml", removed)
        self.assertNotIn("does/not/exist", removed)


class TestFeatureOverride(_ScaffoldHarness):
    """End-to-end: re-bootstrap with a changed selection (the CLI's add/prune flow)."""

    def test_add_feature_promotes_language_and_ships_artifacts(self) -> None:
        target = self._fresh_target()
        self._scaffold_into(target, {"python"})
        self.assertFalse((target / "go.mod").exists())
        self.assertFalse((target / "tools" / "lint" / "linters.bzl").exists())

        # Adding lint promotes go (CLI does this via _promote_for_features).
        self._scaffold_into(target, {"python", "go"}, features={"lint"})
        self.assertTrue((target / "go.mod").exists())
        self.assertTrue((target / "tools" / "lint" / "linters.bzl").exists())
        # Lint deps are now present in requirements.in (re-rendered with lint on).
        self.assertIn("ty", (target / "tools" / "python" / "requirements.in").read_text())

    def test_remove_features_prunes_orphans_and_self_heals_composites(self) -> None:
        target = self._fresh_target()
        self._scaffold_into(target, {"python", "go"}, features={"publish", "lint"})
        # Owner-specific artifacts are present after the first scaffold.
        for rel in ("tools/publish", ".publish.toml", "tools/lint/linters.bzl"):
            self.assertTrue((target / rel).exists(), f"{rel} should exist before pruning")

        # Simulate the CLI: compute the prune set, delete existing paths, re-scaffold.
        prune = compute_prune_set(self.manifest, {"python", "go"}, {"publish", "lint"}, {"python", "go"}, set())
        prune_paths(target, [r for r in prune if (target / r).exists()])
        self._scaffold_into(target, {"python", "go"}, features=set())

        # Owner-specific artifacts are gone.
        for rel in ("tools/publish", ".publish.toml", "tools/lint/linters.bzl"):
            self.assertFalse((target / rel).exists(), f"{rel} should be pruned")
        # Language tooling survives (python is still selected).
        self.assertTrue((target / "tools" / "python").is_dir())
        self.assertTrue((target / "tools" / "python" / "requirements.in").exists())
        # Composite files self-heal: lint deps stripped, unconditional dep kept.
        req = (target / "tools" / "python" / "requirements.in").read_text()
        self.assertIn("pre-commit", req)
        self.assertNotIn("ty", req)


class TestBootstrapMarker(_ScaffoldHarness):
    """The .omniglot_bootstrap.toml marker round-trips the selection exactly."""

    def test_scaffold_writes_marker(self) -> None:
        target = self._fresh_target()
        self._scaffold_into(target, {"python", "go"}, features={"publish"}, module_dir="services")
        marker = read_bootstrap_marker(target, self.manifest)
        if marker is None:
            self.fail("scaffold did not write a readable marker")
        languages, features, module_dir = marker
        self.assertEqual(module_dir, "services")
        self.assertEqual(languages, {"python", "go"})
        self.assertEqual(features, {"publish"})

    def test_read_marker_drops_unknown_keys(self) -> None:
        target = self._fresh_target()
        (target / BOOTSTRAP_MARKER_FILE).write_text(
            '[repo]\nmodule_dir = "m"\nlanguages = ["python", "cobol"]\nfeatures = ["lint", "telepathy"]\n'
        )
        languages, features, module_dir = read_bootstrap_marker(target, self.manifest) or (None, None, None)
        self.assertEqual(languages, {"python"})
        self.assertEqual(features, {"lint"})

    def test_read_marker_absent_or_malformed_is_none(self) -> None:
        target = self._fresh_target()
        self.assertIsNone(read_bootstrap_marker(target, self.manifest))
        (target / BOOTSTRAP_MARKER_FILE).write_text("this is not valid toml = = =")
        self.assertIsNone(read_bootstrap_marker(target, self.manifest))


class TestFeatureRemovers(_ScaffoldHarness):
    """feature_remover_commands — which deselected features get a teardown pass."""

    def test_lint_and_publish_have_removers(self) -> None:
        cmds = dict(feature_remover_commands({"lint", "publish"}))
        self.assertIn("-lint_remove", cmds.get("lint", ""))
        self.assertIn("-publish_remove", cmds.get("publish", ""))

    def test_no_removed_features_no_commands(self) -> None:
        self.assertEqual(feature_remover_commands(set()), [])


if __name__ == "__main__":
    unittest.main()
