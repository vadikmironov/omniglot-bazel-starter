"""Tests for mint.worktree module.

Uses real temporary git repos — no mocking.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path

from mint.worktree import create_worktree, remove_worktree, secure_worktree


def _setup_repo_with_remote() -> tuple[Path, Path]:
    """Create a bare remote and a clone with one commit pushed.

    Returns (clone_path, bare_path).
    """
    tmpdir = Path(tempfile.mkdtemp())
    bare = tmpdir / "remote.git"
    clone = tmpdir / "clone"

    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(bare)],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "clone", str(bare), str(clone)],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=clone,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=clone,
        capture_output=True,
        check=True,
    )
    (clone / "README").write_text("init")
    subprocess.run(["git", "add", "."], cwd=clone, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=clone,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", "main"],
        cwd=clone,
        capture_output=True,
        check=True,
    )
    return clone, bare


class TestCreateWorktree(unittest.TestCase):
    def setUp(self):
        self.clone, self.bare = _setup_repo_with_remote()

    def test_creates_directory(self):
        wt = create_worktree("main", cwd=self.clone)
        try:
            self.assertTrue(wt.exists())
            self.assertTrue(wt.is_dir())
            # Should contain the checked-out file
            self.assertTrue((wt / "README").exists())
        finally:
            remove_worktree(wt, cwd=self.clone)

    def test_restrictive_permissions(self):
        wt = create_worktree("main", cwd=self.clone)
        try:
            mode = oct(wt.stat().st_mode & 0o777)
            self.assertEqual(mode, oct(0o700))
        finally:
            remove_worktree(wt, cwd=self.clone)

    def test_invalid_branch_raises(self):
        with self.assertRaises(RuntimeError):
            create_worktree("nonexistent-branch-xyz", cwd=self.clone)

    def test_detached_head(self):
        wt = create_worktree("main", cwd=self.clone)
        try:
            result = subprocess.run(
                ["git", "symbolic-ref", "HEAD"],
                cwd=wt,
                capture_output=True,
                text=True,
                check=False,
            )
            # Detached HEAD means symbolic-ref fails
            self.assertNotEqual(result.returncode, 0)
        finally:
            remove_worktree(wt, cwd=self.clone)


class TestRemoveWorktree(unittest.TestCase):
    def setUp(self):
        self.clone, self.bare = _setup_repo_with_remote()

    def test_removes_directory(self):
        wt = create_worktree("main", cwd=self.clone)
        self.assertTrue(wt.exists())
        remove_worktree(wt, cwd=self.clone)
        self.assertFalse(wt.exists())

    def test_remove_nonexistent_no_error(self):
        # Should not raise
        remove_worktree(Path(tempfile.gettempdir()) / "nonexistent-mint-test-path", cwd=self.clone)


class TestSecureWorktree(unittest.TestCase):
    def setUp(self):
        self.clone, self.bare = _setup_repo_with_remote()

    def test_yields_valid_path(self):
        with secure_worktree("main", cwd=self.clone) as wt:
            self.assertTrue(wt.exists())
            self.assertTrue((wt / "README").exists())

    def test_cleanup_on_success(self):
        with secure_worktree("main", cwd=self.clone) as wt:
            wt_path = wt
        self.assertFalse(wt_path.exists())

    def test_cleanup_on_exception(self):
        wt_path = None
        try:
            with secure_worktree("main", cwd=self.clone) as wt:
                wt_path = wt
                raise RuntimeError("simulated failure")
        except RuntimeError:
            pass
        self.assertIsNotNone(wt_path)
        self.assertFalse(wt_path.exists())

    def test_worktree_is_independent(self):
        """Changes in worktree don't affect the main repo."""
        with secure_worktree("main", cwd=self.clone) as wt:
            (wt / "new_file").write_text("test")
            subprocess.run(["git", "add", "."], cwd=wt, capture_output=True, check=True)
            subprocess.run(
                ["git", "commit", "-m", "worktree change"],
                cwd=wt,
                capture_output=True,
                text=True,
                check=True,
            )
            # Main repo should not see this file
            self.assertFalse((self.clone / "new_file").exists())


if __name__ == "__main__":
    unittest.main()
