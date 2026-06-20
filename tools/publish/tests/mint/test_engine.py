"""Tests for mint.engine module.

Uses real temporary git repos for build_plan tests.
"""

import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from mint.config import ComponentSetConfig, PublishConfig, SchemaConfig
from mint.engine import (
    INCLUDE_ALL,
    INCLUDE_ARTIFACTS,
    INCLUDE_IMAGES,
    GroupPlan,
    PublishPlan,
    build_plan,
    execute_plan,
    print_plan,
)
from mint.git import create_tag

SEMVER = SchemaConfig(
    release="{major}.{minor}.{patch}",
    development="{next_version}.dev{git_count}+{git_commit}",
    auto_increment="patch",
)


def _make_config(
    component_sets: dict | None = None,
    independent: list | None = None,
    schema: str = "{s}",
) -> PublishConfig:
    sets = {}
    if component_sets:
        for name, modules in component_sets.items():
            sets[name] = ComponentSetConfig(modules=modules)
    return PublishConfig(
        schema=schema,
        schemas={"s": SEMVER},
        component_sets=sets,
        independent=independent or [],
    )


def _init_repo(path: Path) -> None:
    """Initialise a git repo with one commit."""
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=path,
        capture_output=True,
        check=True,
    )
    (path / "README").write_text("init")
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=path,
        capture_output=True,
        check=True,
    )


def _commit(path: Path, msg: str = "change") -> None:
    (path / msg.replace(" ", "_")).write_text(msg)
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=path,
        capture_output=True,
        check=True,
    )


# ── build_plan: dev mode ────────────────────────────────────────────


class TestBuildPlanDev(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo = Path(self.tmpdir)
        _init_repo(self.repo)

    def test_no_tags(self):
        config = _make_config()
        plan = build_plan(config, mode="dev", scope="//modules/foo", cwd=self.repo)
        self.assertEqual(plan.mode, "dev")
        self.assertEqual(len(plan.groups), 1)
        g = plan.groups[0]
        # No prior tag → next is 0.0.1, dev version includes .dev and +
        self.assertIn(".dev", g.raw_version)
        self.assertIn("+", g.raw_version)
        self.assertIsNone(g.tag)

    def test_with_existing_tag(self):
        create_tag("v1.2.3", cwd=self.repo)
        _commit(self.repo, "after-tag")
        config = _make_config()
        plan = build_plan(config, mode="dev", scope="//modules/foo", cwd=self.repo)
        g = plan.groups[0]
        self.assertTrue(g.raw_version.startswith("1.2.4.dev1+"))

    def test_component_set_scope(self):
        config = _make_config(
            component_sets={"backend": ["//modules/a", "//modules/b"]},
        )
        plan = build_plan(config, mode="dev", scope="backend", cwd=self.repo)
        self.assertEqual(len(plan.groups), 1)
        self.assertEqual(plan.groups[0].tag_prefix, "backend/")
        self.assertEqual(plan.groups[0].modules, ["//modules/a", "//modules/b"])

    def test_version_override(self):
        config = _make_config()
        plan = build_plan(
            config,
            mode="dev",
            scope="//modules/foo",
            version_override="1.0.0-custom",
            cwd=self.repo,
        )
        g = plan.groups[0]
        self.assertEqual(g.raw_version, "1.0.0-custom")
        self.assertIsNone(g.tag)


# ── build_plan: release mode ────────────────────────────────────────


class TestBuildPlanRelease(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo = Path(self.tmpdir)
        _init_repo(self.repo)

    def test_no_tags(self):
        config = _make_config()
        plan = build_plan(config, mode="release", scope="//modules/foo", cwd=self.repo)
        g = plan.groups[0]
        self.assertEqual(g.raw_version, "0.0.1")
        self.assertEqual(g.tag, "v0.0.1")

    def test_increment_from_tag(self):
        create_tag("v1.2.3", cwd=self.repo)
        _commit(self.repo, "bump")
        config = _make_config()
        plan = build_plan(config, mode="release", scope="//modules/foo", cwd=self.repo)
        g = plan.groups[0]
        self.assertEqual(g.raw_version, "1.2.4")
        self.assertEqual(g.tag, "v1.2.4")

    def test_version_override(self):
        config = _make_config()
        plan = build_plan(
            config,
            mode="release",
            scope="//modules/foo",
            version_override="9.9.9",
            cwd=self.repo,
        )
        g = plan.groups[0]
        self.assertEqual(g.raw_version, "9.9.9")
        self.assertEqual(g.tag, "v9.9.9")

    def test_prefixed_tag_for_set(self):
        config = _make_config(
            component_sets={"java_all": ["//modules/j1"]},
        )
        plan = build_plan(config, mode="release", scope="java_all", cwd=self.repo)
        g = plan.groups[0]
        self.assertEqual(g.tag, "java_all/v0.0.1")

    def test_prefixed_tag_increment(self):
        create_tag("java_all/v2.0.0", cwd=self.repo)
        _commit(self.repo, "bump")
        config = _make_config(
            component_sets={"java_all": ["//modules/j1"]},
        )
        plan = build_plan(config, mode="release", scope="java_all", cwd=self.repo)
        g = plan.groups[0]
        self.assertEqual(g.raw_version, "2.0.1")
        self.assertEqual(g.tag, "java_all/v2.0.1")


# ── build_plan: edge cases ──────────────────────────────────────────


class TestBuildPlanEdge(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo = Path(self.tmpdir)
        _init_repo(self.repo)

    def test_empty_scope(self):
        config = _make_config()
        plan = build_plan(config, mode="dev", scope=None, cwd=self.repo)
        self.assertEqual(plan.groups, [])

    def test_formatted_version_with_prefix(self):
        config = _make_config(schema="prefix_{s}")
        plan = build_plan(
            config,
            mode="release",
            scope="//modules/foo",
            version_override="1.0.0",
            cwd=self.repo,
        )
        g = plan.groups[0]
        self.assertEqual(g.raw_version, "1.0.0")
        self.assertEqual(g.formatted_version, "prefix_1.0.0")

    def test_branch_stored_in_plan(self):
        config = _make_config()
        plan = build_plan(
            config,
            mode="release",
            scope="//modules/foo",
            branch="main",
            version_override="1.0.0",
            cwd=self.repo,
        )
        self.assertEqual(plan.branch, "main")


# ── execute_plan ─────────────────────────────────────────────────────


class TestExecutePlan(unittest.TestCase):
    def test_empty_plan(self):
        plan = PublishPlan(mode="dev", branch=None, groups=[])
        buf = io.StringIO()
        with redirect_stdout(buf):
            execute_plan(plan, include=INCLUDE_ALL)
        self.assertIn("Nothing to publish", buf.getvalue())

    def test_rejects_unknown_include_value(self):
        plan = PublishPlan(mode="dev", branch=None, groups=[])
        with self.assertRaises(ValueError):
            execute_plan(plan, include="bogus")

    @patch("mint.engine._bazel_target_exists", return_value=False)
    def test_dry_run_prints_plan(self, _mock_exists):
        plan = PublishPlan(
            mode="release",
            branch="main",
            groups=[
                GroupPlan(
                    tag_prefix="",
                    modules=["//modules/foo"],
                    raw_version="1.0.0",
                    formatted_version="1.0.0",
                    tag="v1.0.0",
                ),
            ],
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            execute_plan(plan, include=INCLUDE_ALL, dry_run=True)
        output = buf.getvalue()
        self.assertIn("release", output)
        self.assertIn("1.0.0", output)
        self.assertIn("v1.0.0", output)
        self.assertIn("//modules/foo:publish", output)

    @patch("mint.engine._bazel_target_exists", return_value=False)
    @patch("mint.engine._run_publish")
    def test_dev_calls_run_publish(self, mock_run, _mock_exists):
        plan = PublishPlan(
            mode="dev",
            branch=None,
            groups=[
                GroupPlan(
                    tag_prefix="",
                    modules=["//modules/a", "//modules/b"],
                    raw_version="1.0.0.dev1+abc",
                    formatted_version="1.0.0.dev1+abc",
                    tag=None,
                ),
            ],
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            execute_plan(plan, include=INCLUDE_ALL, cwd=Path(tempfile.gettempdir()))
        self.assertEqual(mock_run.call_count, 2)
        mock_run.assert_any_call("//modules/a:publish", "1.0.0.dev1+abc", "dev", cwd=Path(tempfile.gettempdir()))
        mock_run.assert_any_call("//modules/b:publish", "1.0.0.dev1+abc", "dev", cwd=Path(tempfile.gettempdir()))

    @patch("mint.engine._bazel_target_exists", return_value=True)
    @patch("mint.engine._run_publish")
    def test_dev_runs_artifact_then_image_when_both_exist(self, mock_run, _mock_exists):
        plan = PublishPlan(
            mode="dev",
            branch=None,
            groups=[
                GroupPlan(
                    tag_prefix="",
                    modules=["//modules/java_app"],
                    raw_version="1.0.0",
                    formatted_version="1.0.0",
                    tag=None,
                ),
            ],
        )
        with redirect_stdout(io.StringIO()):
            execute_plan(plan, include=INCLUDE_ALL)
        self.assertEqual(mock_run.call_count, 2)
        # Order matters: artifact first, image second.
        call_targets = [c.args[0] for c in mock_run.call_args_list]
        self.assertEqual(
            call_targets,
            ["//modules/java_app:publish", "//modules/java_app:publish_image"],
        )

    @patch("mint.engine._bazel_target_exists", return_value=False)
    @patch("mint.engine._run_publish")
    def test_dev_skips_image_when_target_absent(self, mock_run, _mock_exists):
        plan = PublishPlan(
            mode="dev",
            branch=None,
            groups=[
                GroupPlan(
                    tag_prefix="",
                    modules=["//modules/java_lib"],
                    raw_version="1.0.0",
                    formatted_version="1.0.0",
                    tag=None,
                ),
            ],
        )
        with redirect_stdout(io.StringIO()):
            execute_plan(plan, include=INCLUDE_ALL)
        self.assertEqual(mock_run.call_count, 1)
        mock_run.assert_called_with("//modules/java_lib:publish", "1.0.0", "dev", cwd=None)

    @patch("mint.engine._bazel_target_exists", return_value=True)
    @patch("mint.engine._run_publish")
    def test_include_artifacts_suppresses_image_track(self, mock_run, _mock_exists):
        plan = PublishPlan(
            mode="dev",
            branch=None,
            groups=[
                GroupPlan(
                    tag_prefix="",
                    modules=["//modules/java_app"],
                    raw_version="1.0.0",
                    formatted_version="1.0.0",
                    tag=None,
                ),
            ],
        )
        with redirect_stdout(io.StringIO()):
            execute_plan(plan, include=INCLUDE_ARTIFACTS)
        self.assertEqual(mock_run.call_count, 1)
        mock_run.assert_called_with("//modules/java_app:publish", "1.0.0", "dev", cwd=None)

    @patch("mint.engine._bazel_target_exists", return_value=True)
    @patch("mint.engine._run_publish")
    def test_include_images_suppresses_artifact_track(self, mock_run, _mock_exists):
        plan = PublishPlan(
            mode="dev",
            branch=None,
            groups=[
                GroupPlan(
                    tag_prefix="",
                    modules=["//modules/java_app"],
                    raw_version="1.0.0",
                    formatted_version="1.0.0",
                    tag=None,
                ),
            ],
        )
        with redirect_stdout(io.StringIO()):
            execute_plan(plan, include=INCLUDE_IMAGES)
        self.assertEqual(mock_run.call_count, 1)
        mock_run.assert_called_with("//modules/java_app:publish_image", "1.0.0", "dev", cwd=None)


class TestPrintPlan(unittest.TestCase):
    @patch("mint.engine._bazel_target_exists", return_value=False)
    def test_dev_plan_output(self, _mock_exists):
        plan = PublishPlan(
            mode="dev",
            branch=None,
            groups=[
                GroupPlan(
                    tag_prefix="backend/",
                    modules=["//modules/a"],
                    raw_version="1.0.0.dev5+abc",
                    formatted_version="1.0.0.dev5+abc",
                    tag=None,
                ),
            ],
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            print_plan(plan)
        output = buf.getvalue()
        self.assertIn("dev", output)
        self.assertIn("backend/", output)
        self.assertIn("//modules/a:publish", output)

    @patch("mint.engine._bazel_target_exists", return_value=False)
    def test_release_plan_with_tag(self, _mock_exists):
        plan = PublishPlan(
            mode="release",
            branch="main",
            groups=[
                GroupPlan(
                    tag_prefix="",
                    modules=["//modules/x"],
                    raw_version="2.0.0",
                    formatted_version="2.0.0",
                    tag="v2.0.0",
                ),
            ],
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            print_plan(plan)
        output = buf.getvalue()
        self.assertIn("Branch: main", output)
        self.assertIn("tag: v2.0.0", output)

    @patch("mint.engine._bazel_target_exists", return_value=True)
    def test_print_plan_shows_image_target_when_present(self, _mock_exists):
        plan = PublishPlan(
            mode="dev",
            branch=None,
            groups=[
                GroupPlan(
                    tag_prefix="",
                    modules=["//modules/java_app"],
                    raw_version="1.0.0",
                    formatted_version="1.0.0",
                    tag=None,
                ),
            ],
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            print_plan(plan)
        output = buf.getvalue()
        self.assertIn("//modules/java_app:publish", output)
        self.assertIn("//modules/java_app:publish_image", output)

    @patch("mint.engine._bazel_target_exists", return_value=True)
    def test_print_plan_annotates_deselected_image_track(self, _mock_exists):
        plan = PublishPlan(
            mode="dev",
            branch=None,
            groups=[
                GroupPlan(
                    tag_prefix="",
                    modules=["//modules/java_app"],
                    raw_version="1.0.0",
                    formatted_version="1.0.0",
                    tag=None,
                ),
            ],
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            print_plan(plan, include=INCLUDE_ARTIFACTS)
        output = buf.getvalue()
        self.assertIn(
            "//modules/java_app:publish_image (skipped: --include-pub-targets=artifacts)",
            output,
        )

    @patch("mint.engine._bazel_target_exists", return_value=True)
    def test_print_plan_annotates_deselected_artifact_track(self, _mock_exists):
        plan = PublishPlan(
            mode="dev",
            branch=None,
            groups=[
                GroupPlan(
                    tag_prefix="",
                    modules=["//modules/java_app"],
                    raw_version="1.0.0",
                    formatted_version="1.0.0",
                    tag=None,
                ),
            ],
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            print_plan(plan, include=INCLUDE_IMAGES)
        output = buf.getvalue()
        self.assertIn(
            "//modules/java_app:publish (skipped: --include-pub-targets=images)",
            output,
        )


if __name__ == "__main__":
    unittest.main()
