"""Git operations for mint.

Tag-based version queries, tag creation/deletion, and push.
All functions accept an optional cwd parameter for worktree support.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def get_last_tag(prefix: str = "", cwd: Path | None = None) -> str | None:
    """Find the most recent tag matching {prefix}v*.

    Returns the full tag string (e.g. "v1.2.3" or "backend/v1.0.0"),
    or None if no matching tag exists.
    """
    pattern = f"{prefix}v*"
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--match", pattern, "--abbrev=0"],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def get_git_count(from_ref: str | None = None, cwd: Path | None = None) -> int:
    """Count commits since from_ref (or total commits if None)."""
    cmd = ["git", "rev-list", "--count", f"{from_ref}..HEAD"] if from_ref else ["git", "rev-list", "--count", "HEAD"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=cwd)
    return int(result.stdout.strip())


def get_git_commit(cwd: Path | None = None) -> str:
    """Return abbreviated commit hash of HEAD."""
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        cwd=cwd,
    )
    return result.stdout.strip()


def create_tag(tag: str, cwd: Path | None = None) -> None:
    """Create a lightweight local tag."""
    subprocess.run(["git", "tag", "--", tag], capture_output=True, text=True, check=True, cwd=cwd)


def delete_tag(tag: str, cwd: Path | None = None) -> None:
    """Delete a local tag. Ignores errors if tag doesn't exist."""
    subprocess.run(["git", "tag", "-d", "--", tag], capture_output=True, text=True, check=False, cwd=cwd)


def push_tags(tags: list[str], remote: str = "origin", cwd: Path | None = None) -> None:
    """Push specific tags to a remote."""
    if not tags:
        return
    subprocess.run(
        ["git", "push", remote, "--"] + tags,
        capture_output=True,
        text=True,
        check=True,
        cwd=cwd,
    )


def validate_branch_exists(branch: str, remote: str = "origin", cwd: Path | None = None) -> None:
    """Verify that a remote branch exists. Raises on failure."""
    ref = f"refs/remotes/{remote}/{branch}"
    result = subprocess.run(
        ["git", "rev-parse", "--verify", ref],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
    )
    if result.returncode != 0:
        raise ValueError(
            f"Branch '{branch}' not found on remote '{remote}'. Ensure the branch exists and has been fetched."
        )


def tag_version_string(prefix: str, version: str) -> str:
    """Format a version into a tag string.

    Examples:
        ("", "1.2.3")           -> "v1.2.3"
        ("backend/", "1.0.0")   -> "backend/v1.0.0"
    """
    return f"{prefix}v{version}"


def parse_tag_version(tag: str, prefix: str = "") -> str:
    """Extract the version string from a tag.

    Strips the prefix and leading 'v'.

    Examples:
        ("v1.2.3", "")             -> "1.2.3"
        ("backend/v1.0.0", "backend/") -> "1.0.0"
    """
    expected_prefix = f"{prefix}v"
    if not tag.startswith(expected_prefix):
        raise ValueError(f"Tag '{tag}' does not match expected prefix '{expected_prefix}'")
    return tag[len(expected_prefix) :]
