"""Re-bootstrap behavior — user-managed regions survive a second scaffold.

Scaffolds into a temp dir, simulates a user editing the user-managed region
of a managed dependency file, then scaffolds again into the same dir and
verifies the edit survived while the starter baseline stayed intact.
"""

import contextlib
import hashlib
import io
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from datetime import UTC, datetime
from pathlib import Path

from bootstrap.detect import detect_repo
from bootstrap.manifest import (
    BOOTSTRAP_MARKER_FILE,
    UNVERIFIED,
    BootstrapManifest,
    compute_prune_set,
    file_fingerprint,
    load_manifest,
    orphan_status,
    read_bootstrap_inventory,
    read_bootstrap_marker,
    read_bootstrap_orphans,
    resolve_files,
    starter_revision,
    unignored_files,
    write_bootstrap_marker,
)
from bootstrap.processor import has_user_region
from bootstrap.scaffolder import (
    ConfirmOverwrite,
    ScaffoldResult,
    _make_ignore,
    feature_remover_commands,
    prunable_orphans,
    prune_orphans,
    prune_paths,
    scaffold_repo,
)

TEST_REPO_NAME = "rebootstrap_test"

# Source-repo paths of the managed dependency files (relative to repo root).
MANAGED_SOURCE_FILES = [
    ".gitignore",
    ".bazelignore",
    "bazel_downloader.cfg",
    ".clang-tidy",
    "tools/python/pyproject.toml",
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
        confirm: ConfirmOverwrite | None = None,
    ) -> ScaffoldResult:
        features = features or set()
        resolved = resolve_files(self.manifest, selected, features)
        return scaffold_repo(
            confirm=confirm,
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
        req = target / "tools" / "python" / "pyproject.toml"

        # User appends a dependency inside the user-managed region.
        edited = req.read_text().replace(
            "    # --- END user-managed ---",
            '    "flask==3.0.0",\n    # --- END user-managed ---',
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
        req = target / "tools" / "python" / "pyproject.toml"
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

    def test_bazelignore_user_edit_survives(self) -> None:
        target = self._fresh_target()
        self._scaffold_into(target, {"python"})
        bi = target / ".bazelignore"

        # User appends a project-specific ignore inside the user-managed region.
        edited = bi.read_text().replace(
            "# --- END user-managed ---",
            "services/postgres/data\n# --- END user-managed ---",
            1,
        )
        bi.write_text(edited)

        self._scaffold_into(target, {"python"})  # re-bootstrap
        result = bi.read_text()
        self.assertIn("services/postgres/data", result, "user bazelignore entry lost on re-bootstrap")
        # The bazel-* symlink ignores prove the baseline was refreshed alongside.
        self.assertIn("bazel-out", result, "starter baseline lost on re-bootstrap")

    def test_downloader_cfg_user_rule_survives(self) -> None:
        target = self._fresh_target()
        self._scaffold_into(target, {"python"})
        cfg = target / "bazel_downloader.cfg"

        # User adds a proxy rewrite inside the user-managed region.
        rule = "rewrite github.com/(.*) proxy.example.com/github/$1"
        cfg.write_text(cfg.read_text().replace("# --- END user-managed ---", f"{rule}\n# --- END user-managed ---", 1))

        self._scaffold_into(target, {"python"})  # re-bootstrap
        result = cfg.read_text()
        self.assertIn(rule, result, "user downloader rule lost on re-bootstrap")
        self.assertIn("Bazel downloader configuration", result, "starter baseline lost on re-bootstrap")

    def test_file_predating_its_user_region_is_replaced_with_a_note(self) -> None:
        """A target written before its file gained a region has nothing to
        splice: it is replaced, and the run says so."""
        target = self._fresh_target()
        self._scaffold_into(target, {"python"})
        cfg = target / "bazel_downloader.cfg"
        cfg.write_text("rewrite github.com/(.*) proxy.example.com/github/$1\n")  # no region

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self._scaffold_into(target, {"python"})  # re-bootstrap
        self.assertTrue(has_user_region(cfg.read_text()), "replaced file should carry the region")
        self.assertIn("had no user-managed region and was replaced", out.getvalue())

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self._scaffold_into(target, {"python"})  # region present now: no note
        self.assertNotIn("had no user-managed region", out.getvalue())

    def test_clang_tidy_user_edit_stays_inside_checks(self) -> None:
        target = self._fresh_target()
        self._scaffold_into(target, {"cpp"})
        tidy = target / ".clang-tidy"

        # User disables a check inside the user-managed region (a list item).
        edited = tidy.read_text().replace(
            "  # --- END user-managed ---",
            "  - '-readability-magic-numbers'\n  # --- END user-managed ---",
            1,
        )
        tidy.write_text(edited)

        self._scaffold_into(target, {"cpp"})  # re-bootstrap
        result = tidy.read_text()
        self.assertIn("- '-readability-magic-numbers'", result, "user check glob lost on re-bootstrap")
        # Starter globs prove the baseline was refreshed alongside the user region.
        self.assertIn("- '-bugprone-easily-swappable-parameters'", result, "starter baseline lost on re-bootstrap")
        # The user glob must stay a member of the Checks list — after the
        # starter globs (last match wins) and before the next top-level key.
        self.assertGreater(
            result.index("- '-readability-magic-numbers'"),
            result.index("- '-bugprone-easily-swappable-parameters'"),
            "user glob precedes the starter globs",
        )
        self.assertLess(
            result.index("- '-readability-magic-numbers'"),
            result.index("WarningsAsErrors:"),
            "user glob escaped the Checks list",
        )

    def test_gomod_is_not_managed(self) -> None:
        """go.mod carries no user-managed region — it is import-driven (tidy)."""
        target = self._fresh_target()
        self._scaffold_into(target, {"go"})
        gomod = (target / "go.mod").read_text()
        self.assertFalse(has_user_region(gomod), "go.mod should not be a managed file")


class TestReviewComparesLikeWithLike(_ScaffoldHarness):
    """``--review`` compares the rendered file after the repo rename, as the
    file on disk already is."""

    def _recording_confirm(self) -> tuple[list[tuple[str, str, str]], ConfirmOverwrite]:
        calls: list[tuple[str, str, str]] = []

        def confirm(dst: Path, existing: str, new_content: str) -> bool:
            calls.append((dst.name, existing, new_content))
            return True

        return calls, confirm

    def test_an_unedited_repo_is_not_asked_about(self) -> None:
        """The rename alone is no difference: nothing to review."""
        target = self._fresh_target()
        self._scaffold_into(target, {"python"})
        self.assertIn(TEST_REPO_NAME, (target / "MODULE.bazel").read_text())

        calls, confirm = self._recording_confirm()
        self._scaffold_into(target, {"python"}, confirm=confirm)
        self.assertEqual([name for name, _, _ in calls], [])

    def test_a_real_edit_is_shown_without_the_rename(self) -> None:
        target = self._fresh_target()
        self._scaffold_into(target, {"python"})
        module = target / "MODULE.bazel"
        module.write_text(module.read_text() + "# a local edit outside any user-managed region\n")

        calls, confirm = self._recording_confirm()
        self._scaffold_into(target, {"python"}, confirm=confirm)
        self.assertEqual([name for name, _, _ in calls], ["MODULE.bazel"])
        _, existing, new_content = calls[0]
        self.assertNotIn(self.manifest.original_name, new_content, "the starter's name must not be offered")
        changed = set(existing.splitlines()) ^ set(new_content.splitlines())
        self.assertEqual(changed, {"# a local edit outside any user-managed region"})


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
        # Lint deps are now present in pyproject.toml (re-rendered with lint on).
        self.assertIn("ty", (target / "tools" / "python" / "pyproject.toml").read_text())

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
        self.assertTrue((target / "tools" / "python" / "pyproject.toml").exists())
        # Composite files self-heal: lint deps stripped, unconditional dep kept.
        req = (target / "tools" / "python" / "pyproject.toml").read_text()
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

    def test_marker_records_when_the_scaffold_was_written(self) -> None:
        # Nothing reads it back; it exists so a stale generated file can be
        # dated against the starter's history.
        target = self._fresh_target()
        before = datetime.now(UTC).replace(microsecond=0)
        self._scaffold_into(target, {"python"})
        stamp = tomllib.loads((target / BOOTSTRAP_MARKER_FILE).read_text())["repo"]["bootstrapped_at"]
        written = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        self.assertGreaterEqual(written, before)
        self.assertLessEqual(written, datetime.now(UTC))

    def test_rebootstrap_refreshes_the_timestamp(self) -> None:
        target = self._fresh_target()
        self._scaffold_into(target, {"python"})
        marker = target / BOOTSTRAP_MARKER_FILE
        marker.write_text(
            marker.read_text().replace(
                tomllib.loads(marker.read_text())["repo"]["bootstrapped_at"], "2000-01-01T00:00:00Z"
            )
        )
        self._scaffold_into(target, {"python"})
        refreshed = tomllib.loads(marker.read_text())["repo"]["bootstrapped_at"]
        self.assertNotEqual(refreshed, "2000-01-01T00:00:00Z")

    def test_marker_records_the_starter_revision(self) -> None:
        # The source root is this repo, so the scaffold should be pinned to a
        # real commit — that is what dates a generated file exactly.
        target = self._fresh_target()
        self._scaffold_into(target, {"python"})
        repo = tomllib.loads((target / BOOTSTRAP_MARKER_FILE).read_text())["repo"]
        revision = repo["starter_revision"]
        sha = revision.removesuffix("-dirty")
        self.assertRegex(sha, r"^[0-9a-f]{40}$")
        head = subprocess.run(  # noqa: S603
            ["git", "-C", str(self.source_root), "rev-parse", "HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        self.assertEqual(sha, head)

    def test_starter_revision_omitted_outside_a_git_checkout(self) -> None:
        # Scaffolding from an unpacked tarball is legitimate; the field is
        # dropped rather than recorded as a guess.
        target = self._fresh_target()
        self.assertIsNone(starter_revision(target))  # fresh temp dir, no git
        write_bootstrap_marker(target, "modules", {"python"}, set(), source_root=target)
        repo = tomllib.loads((target / BOOTSTRAP_MARKER_FILE).read_text())["repo"]
        self.assertNotIn("starter_revision", repo)
        self.assertIn("bootstrapped_at", repo)

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

    def test_inventory_round_trips(self) -> None:
        """Files, a symlink and a path that needs quoting all come back; a
        listed path that is not on disk is left out."""
        target = self._fresh_target()
        (target / "tools").mkdir()
        (target / "tools" / "a.txt").write_text("alpha\n")
        (target / 'odd "name".txt').write_text("quoted\n")
        (target / "link").symlink_to("tools/a.txt")
        rels = ["tools/a.txt", 'odd "name".txt', "link", "never/written.txt"]
        write_bootstrap_marker(target, "modules", {"python"}, set(), files=rels)

        inventory = read_bootstrap_inventory(target)
        self.assertEqual(
            inventory,
            {
                "tools/a.txt": "sha256:" + hashlib.sha256(b"alpha\n").hexdigest(),
                'odd "name".txt': "sha256:" + hashlib.sha256(b"quoted\n").hexdigest(),
                "link": "symlink:tools/a.txt",
            },
        )
        # The selection still reads back beside the new table.
        self.assertEqual(read_bootstrap_marker(target, self.manifest), ({"python"}, set(), "modules"))

    def test_inventory_absent_from_an_older_marker_is_none(self) -> None:
        """None means "nothing recorded", which an empty table does not."""
        target = self._fresh_target()
        self.assertIsNone(read_bootstrap_inventory(target))
        write_bootstrap_marker(target, "modules", {"python"}, set())
        self.assertIsNone(read_bootstrap_inventory(target))
        write_bootstrap_marker(target, "modules", {"python"}, set(), files=[])
        self.assertEqual(read_bootstrap_inventory(target), {})

    def test_rebootstrap_refreshes_the_inventory(self) -> None:
        """A re-bootstrap re-records fingerprints, so an edit inside a
        user-managed region shows up as that file's new fingerprint."""
        target = self._fresh_target()
        self._scaffold_into(target, {"python"})
        before = read_bootstrap_inventory(target) or {}
        bi = target / ".bazelignore"
        bi.write_text(bi.read_text().replace("# --- END user-managed ---", "data\n# --- END user-managed ---", 1))

        self._scaffold_into(target, {"python"})
        after = read_bootstrap_inventory(target) or {}
        self.assertEqual(set(after), set(before))
        self.assertNotEqual(after[".bazelignore"], before[".bazelignore"])
        self.assertEqual(after[".bazelignore"], file_fingerprint(bi))


class TestOrphans(_ScaffoldHarness):
    """Files an earlier run recorded that the starter no longer ships."""

    def _plant(self, target: Path, rel: str, content: str = "left behind\n") -> None:
        """Make *rel* look like a file the previous run managed: on disk, and in
        the recorded inventory — which is all a dropped starter file is."""
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        inventory = read_bootstrap_inventory(target) or {}
        write_bootstrap_marker(
            target, "modules", {"python"}, set(), files=[*inventory, rel], orphans=read_bootstrap_orphans(target)
        )

    def test_clean_rebootstrap_has_no_orphans(self) -> None:
        target = self._fresh_target()
        self.assertEqual(self._scaffold_into(target, {"python"}).orphans, {})
        self.assertEqual(self._scaffold_into(target, {"python"}).orphans, {})
        self.assertEqual(read_bootstrap_orphans(target), {})

    def test_dropped_file_is_reported_and_recorded(self) -> None:
        target = self._fresh_target()
        self._scaffold_into(target, {"python"})
        self._plant(target, "tools/python/patches/old.patch")

        result = self._scaffold_into(target, {"python"})
        self.assertEqual(set(result.orphans), {"tools/python/patches/old.patch"})
        self.assertNotIn("tools/python/patches/old.patch", result.files)
        self.assertEqual(read_bootstrap_orphans(target), result.orphans)
        self.assertNotIn("tools/python/patches/old.patch", read_bootstrap_inventory(target) or {})

    def test_orphan_is_carried_until_it_is_dealt_with(self) -> None:
        """The second run's [files] no longer lists it; [orphans] must."""
        target = self._fresh_target()
        self._scaffold_into(target, {"python"})
        self._plant(target, "tools/python/old.bzl")
        self._scaffold_into(target, {"python"})

        again = self._scaffold_into(target, {"python"})
        self.assertEqual(set(again.orphans), {"tools/python/old.bzl"})

        (target / "tools/python/old.bzl").unlink()  # the user removed it by hand
        self.assertEqual(self._scaffold_into(target, {"python"}).orphans, {})
        self.assertEqual(read_bootstrap_orphans(target), {})

    def test_modified_is_judged_against_the_recorded_fingerprint(self) -> None:
        target = self._fresh_target()
        self._scaffold_into(target, {"python"})
        self._plant(target, "tools/python/old.bzl", "as the tool left it\n")
        orphans = self._scaffold_into(target, {"python"}).orphans
        recorded = orphans["tools/python/old.bzl"]
        self.assertEqual(orphan_status(target, "tools/python/old.bzl", recorded), "unmodified")

        (target / "tools/python/old.bzl").write_text("edited since\n")
        self.assertEqual(orphan_status(target, "tools/python/old.bzl", recorded), "modified locally")
        # A later run keeps the fingerprint the tool recorded, not the edited one.
        self.assertEqual(self._scaffold_into(target, {"python"}).orphans["tools/python/old.bzl"], recorded)

    def test_a_file_that_ships_again_stops_being_an_orphan(self) -> None:
        target = self._fresh_target()
        self._scaffold_into(target, {"python"})
        shipped = "tools/python/pyproject.toml"
        inventory = read_bootstrap_inventory(target) or {}
        write_bootstrap_marker(
            target, "modules", {"python"}, set(), files=list(inventory), orphans={shipped: inventory[shipped]}
        )
        self.assertEqual(self._scaffold_into(target, {"python"}).orphans, {})

    def test_module_dir_is_never_reported(self) -> None:
        target = self._fresh_target()
        self._scaffold_into(target, {"python"})
        self._plant(target, "modules/app/BUILD")
        self.assertEqual(self._scaffold_into(target, {"python"}).orphans, {})

    def test_deselected_owner_files_left_on_disk_are_orphans(self) -> None:
        """Declining the deselected-owner prompt leaves them behind; they are
        still files the tool wrote and no longer manages."""
        target = self._fresh_target()
        self._scaffold_into(target, {"python", "rust"})
        orphans = self._scaffold_into(target, {"python"}).orphans  # rust dropped, nothing pruned
        self.assertIn("tools/rust/Cargo.toml", orphans)
        self.assertFalse(any(rel.startswith("tools/python/") for rel in orphans))

    def test_prune_spares_what_the_user_just_declined_to_delete(self) -> None:
        paths = ["tools/rust/Cargo.toml", "tools/rust/sub/x.bzl", "tools/rusty.bzl", ".rustfmt.toml", "old.patch"]
        orphans = dict.fromkeys(paths, "sha256:0")
        declined = ["tools/rust", ".rustfmt.toml"]
        self.assertEqual(
            prunable_orphans(orphans, declined, include_unverified=False), ["old.patch", "tools/rusty.bzl"]
        )
        self.assertEqual(prunable_orphans(orphans, [], include_unverified=False), sorted(paths))

    def test_prune_orphans_removes_the_directories_it_empties(self) -> None:
        target = self._fresh_target()
        self._scaffold_into(target, {"python"})
        self._plant(target, "tools/python/patches/deep/old.patch")
        self._plant(target, "tools/python/old.bzl")

        removed = prune_orphans(target, ["tools/python/patches/deep/old.patch", "tools/python/old.bzl", "gone.txt"])
        self.assertEqual(removed, ["tools/python/old.bzl", "tools/python/patches/deep/old.patch"])
        self.assertFalse((target / "tools/python/patches").exists(), "emptied directories should go")
        self.assertTrue((target / "tools/python/pyproject.toml").is_file(), "a directory with content stays")


class TestFirstRunInference(_ScaffoldHarness):
    """A repo bootstrapped before the inventory existed: infer once, from disk."""

    def _predating_repo(self) -> Path:
        """A scaffolded repo whose marker has no [files], as older ones do."""
        target = self._fresh_target()
        self._scaffold_into(target, {"python"})
        write_bootstrap_marker(target, "modules", {"python"}, set())
        return target

    def test_stray_file_in_a_tool_directory_is_an_unverified_orphan(self) -> None:
        target = self._predating_repo()
        (target / "tools/python/patches").mkdir()
        (target / "tools/python/patches/old.patch").write_text("dropped by the starter, or the user's\n")

        result = self._scaffold_into(target, {"python"})
        self.assertEqual(result.orphans, {"tools/python/patches/old.patch": UNVERIFIED})
        self.assertEqual(read_bootstrap_orphans(target), result.orphans)
        self.assertEqual(orphan_status(target, "tools/python/patches/old.patch", UNVERIFIED), UNVERIFIED)

    def test_only_directories_the_scaffold_writes_into_are_examined(self) -> None:
        target = self._predating_repo()
        for rel in ("stray_at_root.txt", "modules/app/BUILD", "tools/mytool/run.sh", "tools/rust/Cargo.toml"):
            (target / rel).parent.mkdir(parents=True, exist_ok=True)
            (target / rel).write_text("not the tool's business\n")
        self.assertEqual(self._scaffold_into(target, {"python"}).orphans, {})

    def test_files_the_repo_ignores_are_not_candidates(self) -> None:
        target = self._predating_repo()
        (target / "tools/python/__pycache__").mkdir()
        (target / "tools/python/__pycache__/x.cpython-314.pyc").write_text("debris\n")
        self.assertEqual(self._scaffold_into(target, {"python"}).orphans, {})

    def test_inference_happens_once(self) -> None:
        """The first run records an inventory; after that the answer is exact."""
        target = self._predating_repo()
        self._scaffold_into(target, {"python"})
        (target / "tools/python/added_later.py").write_text("the user's\n")
        self.assertEqual(self._scaffold_into(target, {"python"}).orphans, {})

    def test_an_unverified_orphan_is_carried_like_any_other(self) -> None:
        target = self._predating_repo()
        (target / "tools/python/old.bzl").write_text("x\n")
        self._scaffold_into(target, {"python"})
        self.assertEqual(self._scaffold_into(target, {"python"}).orphans, {"tools/python/old.bzl": UNVERIFIED})

    def test_a_fresh_target_infers_nothing(self) -> None:
        """No marker means not a bootstrapped repo: whatever is there is the user's."""
        target = self._fresh_target()
        (target / "tools/python").mkdir(parents=True)
        (target / "tools/python/mine.py").write_text("x\n")
        self.assertEqual(self._scaffold_into(target, {"python"}).orphans, {})

    def test_prune_takes_unverified_orphans_only_file_by_file(self) -> None:
        orphans = {"tools/python/old.bzl": UNVERIFIED, "tools/python/dropped.patch": "sha256:0"}
        self.assertEqual(prunable_orphans(orphans, [], include_unverified=False), ["tools/python/dropped.patch"])
        self.assertEqual(prunable_orphans(orphans, [], include_unverified=True), sorted(orphans))


class TestIgnoredFilesStayBehind(_ScaffoldHarness):
    """A directory copy ships what git does not ignore, not the checkout's debris."""

    def _git_checkout(self) -> Path:
        repo = self._fresh_target()
        for args in (["init", "-q"], ["config", "user.email", "t@example.invalid"], ["config", "user.name", "t"]):
            subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)  # noqa: S603, S607
        (repo / ".gitignore").write_text("__pycache__/\n*.pyc\n")
        (repo / "tools/x/tests/__pycache__").mkdir(parents=True)
        (repo / "tools/x/tracked.py").write_text("tracked\n")
        (repo / "tools/x/tests/test_x.py").write_text("tracked\n")
        (repo / "tools/x/tests/__pycache__/test_x.cpython-314.pyc").write_text("debris\n")
        (repo / "tools/x/stray.pyc").write_text("debris\n")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)  # noqa: S603, S607
        subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"], check=True, capture_output=True)  # noqa: S603, S607
        (repo / "tools/x/work_in_progress.py").write_text("untracked, not ignored\n")
        return repo

    def test_unignored_files_are_tracked_plus_unignored_untracked(self) -> None:
        repo = self._git_checkout()
        self.assertEqual(
            unignored_files(repo, "tools/x"),
            {"tools/x/tracked.py", "tools/x/tests/test_x.py", "tools/x/work_in_progress.py"},
        )

    def test_outside_a_git_checkout_nothing_is_filtered(self) -> None:
        self.assertIsNone(unignored_files(self._fresh_target(), "tools/x"))

    def test_directory_copy_leaves_ignored_files_behind(self) -> None:
        repo = self._git_checkout()
        kept = unignored_files(repo, "tools/x") or set()
        dst = self._fresh_target() / "x"
        shutil.copytree(repo / "tools/x", dst, ignore=_make_ignore(set(), {repo / rel for rel in kept}))
        copied = {path.relative_to(dst).as_posix() for path in dst.rglob("*") if path.is_file()}
        self.assertEqual(copied, {"tracked.py", "tests/test_x.py", "work_in_progress.py"})
        self.assertFalse((dst / "tests/__pycache__").exists(), "a directory with only debris should not be created")

    def test_without_a_keep_set_everything_is_copied(self) -> None:
        repo = self._git_checkout()
        dst = self._fresh_target() / "x"
        shutil.copytree(repo / "tools/x", dst, ignore=_make_ignore(set()))
        self.assertTrue((dst / "stray.pyc").is_file())


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
