"""Secure git worktree management for mint.

Provides worktree creation with restrictive permissions and
a context manager that guarantees cleanup.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path


def create_worktree(branch: str, remote: str = "origin", cwd: Path | None = None) -> Path:
    """Create a git worktree in a secure temporary directory.

    The worktree is checked out at a detached HEAD pointing to
    the remote branch tip. The temp directory has mode 0o700.

    Args:
        branch: Branch name (e.g. "main").
        remote: Remote name (default "origin").
        cwd: Working directory for git commands.

    Returns:
        Path to the worktree root.
    """
    worktree_dir = tempfile.mkdtemp(prefix="mint-worktree-")
    Path(worktree_dir).chmod(0o700)
    try:
        subprocess.run(
            [
                "git",
                "worktree",
                "add",
                "--detach",
                worktree_dir,
                "--",
                f"{remote}/{branch}",
            ],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )
    except subprocess.CalledProcessError as exc:
        # Clean up the temp dir if worktree creation fails
        shutil.rmtree(worktree_dir, ignore_errors=True)
        raise RuntimeError(f"Failed to create worktree for {remote}/{branch}: {exc.stderr.strip()}") from exc
    return Path(worktree_dir)


def remove_worktree(worktree_path: Path, cwd: Path | None = None) -> None:
    """Remove a git worktree and its directory.

    Calls `git worktree remove --force` then removes the directory
    if it still exists. Errors are suppressed for cleanup resilience.
    """
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(worktree_path)],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
    )
    if worktree_path.exists():
        shutil.rmtree(worktree_path, ignore_errors=True)


@contextmanager
def secure_worktree(branch: str, remote: str = "origin", cwd: Path | None = None):
    """Context manager that creates and cleans up a worktree.

    Usage:
        with secure_worktree("main") as path:
            # path is a Path to the worktree root
            subprocess.run(["bazel", "build", ...], cwd=path)
    """
    worktree_path = create_worktree(branch, remote=remote, cwd=cwd)
    try:
        yield worktree_path
    finally:
        remove_worktree(worktree_path, cwd=cwd)
