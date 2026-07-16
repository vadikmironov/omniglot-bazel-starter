"""Tests for mint.git module.

Uses real temporary git repos — no mocking of git operations.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path

from mint.git import (
    create_tag,
    delete_tag,
    get_git_commit,
    get_git_count,
    get_last_tag,
    parse_tag_version,
    tag_version_string,
    validate_branch_exists,
)


def _init_repo(path: Path) -> None:
    """Initialise a git repo with one commit."""
    subprocess.run(["git", "init", "-b", "main"], cwd=path, capture_output=True, check=True)
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
    # Create initial commit
    (path / "README").write_text("init")
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=path,
        capture_output=True,
        check=True,
    )


def _commit(path: Path, msg: str = "change") -> None:
    """Create a file and commit it."""
    (path / msg.replace(" ", "_")).write_text(msg)
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=path,
        capture_output=True,
        check=True,
    )


class TestGetLastTag(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo = Path(self.tmpdir)
        _init_repo(self.repo)

    def test_no_tags(self):
        result = get_last_tag(cwd=self.repo)
        self.assertIsNone(result)

    def test_single_tag(self):
        create_tag("v1.0.0", cwd=self.repo)
        result = get_last_tag(cwd=self.repo)
        self.assertEqual(result, "v1.0.0")

    def test_multiple_tags_returns_latest(self):
        create_tag("v1.0.0", cwd=self.repo)
        _commit(self.repo, "second")
        create_tag("v1.1.0", cwd=self.repo)
        result = get_last_tag(cwd=self.repo)
        self.assertEqual(result, "v1.1.0")

    def test_prefix_filtering(self):
        create_tag("v1.0.0", cwd=self.repo)
        create_tag("backend/v2.0.0", cwd=self.repo)
        result = get_last_tag(prefix="backend/", cwd=self.repo)
        self.assertEqual(result, "backend/v2.0.0")

    def test_prefix_excludes_other(self):
        create_tag("v1.0.0", cwd=self.repo)
        result = get_last_tag(prefix="backend/", cwd=self.repo)
        self.assertIsNone(result)

    def test_repo_wide_prefix_ignores_scoped(self):
        create_tag("backend/v2.0.0", cwd=self.repo)
        result = get_last_tag(prefix="", cwd=self.repo)
        # git describe --match "v*" should NOT match "backend/v2.0.0"
        self.assertIsNone(result)


class TestGetGitCount(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo = Path(self.tmpdir)
        _init_repo(self.repo)

    def test_total_commits(self):
        count = get_git_count(cwd=self.repo)
        self.assertEqual(count, 1)

    def test_commits_after_more(self):
        _commit(self.repo, "two")
        _commit(self.repo, "three")
        count = get_git_count(cwd=self.repo)
        self.assertEqual(count, 3)

    def test_commits_since_tag(self):
        create_tag("v1.0.0", cwd=self.repo)
        _commit(self.repo, "after-tag-1")
        _commit(self.repo, "after-tag-2")
        count = get_git_count(from_ref="v1.0.0", cwd=self.repo)
        self.assertEqual(count, 2)

    def test_zero_since_tag(self):
        create_tag("v1.0.0", cwd=self.repo)
        count = get_git_count(from_ref="v1.0.0", cwd=self.repo)
        self.assertEqual(count, 0)


class TestGetGitCommit(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo = Path(self.tmpdir)
        _init_repo(self.repo)

    def test_returns_short_hash(self):
        commit = get_git_commit(cwd=self.repo)
        self.assertTrue(len(commit) >= 7)
        # Should be valid hex
        int(commit, 16)

    def test_changes_after_commit(self):
        commit1 = get_git_commit(cwd=self.repo)
        _commit(self.repo, "new")
        commit2 = get_git_commit(cwd=self.repo)
        self.assertNotEqual(commit1, commit2)


class TestCreateDeleteTag(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo = Path(self.tmpdir)
        _init_repo(self.repo)

    def test_create_and_find(self):
        create_tag("v1.0.0", cwd=self.repo)
        self.assertEqual(get_last_tag(cwd=self.repo), "v1.0.0")

    def test_create_prefixed(self):
        create_tag("backend/v1.0.0", cwd=self.repo)
        self.assertEqual(get_last_tag(prefix="backend/", cwd=self.repo), "backend/v1.0.0")

    def test_delete_removes_tag(self):
        create_tag("v1.0.0", cwd=self.repo)
        delete_tag("v1.0.0", cwd=self.repo)
        self.assertIsNone(get_last_tag(cwd=self.repo))

    def test_delete_nonexistent_no_error(self):
        # Should not raise
        delete_tag("v99.99.99", cwd=self.repo)


class TestValidateBranchExists(unittest.TestCase):
    def setUp(self):
        # Create a bare "remote" and a clone to simulate remote branches
        self.tmpdir = tempfile.mkdtemp()
        self.bare = Path(self.tmpdir) / "bare.git"
        self.clone = Path(self.tmpdir) / "clone"

        subprocess.run(
            ["git", "init", "--bare", "-b", "main", str(self.bare)],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "clone", str(self.bare), str(self.clone)],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=self.clone,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=self.clone,
            capture_output=True,
            check=True,
        )
        # Push initial commit
        (self.clone / "README").write_text("init")
        subprocess.run(["git", "add", "."], cwd=self.clone, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=self.clone,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", "main"],
            cwd=self.clone,
            capture_output=True,
            check=True,
        )

    def test_existing_branch(self):
        # Should not raise
        validate_branch_exists("main", cwd=self.clone)

    def test_missing_branch(self):
        with self.assertRaises(ValueError, msg="not found"):
            validate_branch_exists("nonexistent", cwd=self.clone)


class TestTagVersionString(unittest.TestCase):
    def test_repo_wide(self):
        self.assertEqual(tag_version_string("", "1.2.3"), "v1.2.3")

    def test_with_prefix(self):
        self.assertEqual(tag_version_string("backend/", "1.0.0"), "backend/v1.0.0")

    def test_calver(self):
        self.assertEqual(tag_version_string("", "2026.04.07"), "v2026.04.07")


class TestParseTagVersion(unittest.TestCase):
    def test_repo_wide(self):
        self.assertEqual(parse_tag_version("v1.2.3"), "1.2.3")

    def test_with_prefix(self):
        self.assertEqual(parse_tag_version("backend/v1.0.0", "backend/"), "1.0.0")

    def test_calver(self):
        self.assertEqual(parse_tag_version("v2026.04.07"), "2026.04.07")

    def test_gitdate(self):
        self.assertEqual(parse_tag_version("v2026.04.07.42"), "2026.04.07.42")

    def test_mismatched_prefix(self):
        with self.assertRaises(ValueError):
            parse_tag_version("v1.0.0", "backend/")

    def test_no_v_prefix(self):
        with self.assertRaises(ValueError):
            parse_tag_version("1.0.0")


if __name__ == "__main__":
    unittest.main()
