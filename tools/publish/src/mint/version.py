"""Version resolution for mint.

Handles semver, calver, and gitdate schemas with auto-increment
and dev/release version computation.
"""

from __future__ import annotations

import datetime
import re

from mint.config import SchemaConfig


def parse_semver(version: str) -> tuple[int, int, int]:
    """Parse a semver string into (major, minor, patch).

    Accepts versions with optional pre-release/build metadata suffixes
    but only parses the major.minor.patch prefix.
    """
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        raise ValueError(f"Cannot parse semver from: {version}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def increment_semver(major: int, minor: int, patch: int, component: str) -> tuple[int, int, int]:
    """Increment a semver tuple by the given component."""
    if component == "patch":
        return major, minor, patch + 1
    elif component == "minor":
        return major, minor + 1, 0
    elif component == "major":
        return major + 1, 0, 0
    else:
        raise ValueError(f"Invalid auto_increment component: {component}")


def resolve_release_version(
    schema: SchemaConfig,
    last_version: str | None,
    git_count: int = 0,
    now: datetime.date | None = None,
) -> str:
    """Compute the next release version for a schema.

    Args:
        schema: The schema configuration.
        last_version: The version string from the last tag (None if no prior tags).
        git_count: Commits since last tag (for gitdate schema).
        now: Override for current date (for testing).
    """
    today = now or datetime.date.today()
    template = schema.release

    # Detect schema type from placeholders
    has_semver = "{major}" in template
    has_calver = "{YYYY}" in template
    has_git_count = "{git_count}" in template

    if has_semver:
        return _resolve_semver_release(schema, last_version)
    elif has_calver and has_git_count:
        return _resolve_gitdate_release(template, git_count, today)
    elif has_calver:
        return _resolve_calver_release(template, last_version, today)
    else:
        raise ValueError(f"Cannot determine schema type from template: {template}")


def resolve_dev_version(
    schema: SchemaConfig,
    next_release: str,
    git_count: int,
    git_commit: str,
    now: datetime.date | None = None,
) -> str:
    """Compute a development version string.

    Substitutes {next_version}, {git_count}, {git_commit}, {timestamp}
    into the schema's development template.
    """
    today = now or datetime.date.today()
    version = schema.development
    version = version.replace("{next_version}", next_release)
    version = version.replace("{git_count}", str(git_count))
    version = version.replace("{git_commit}", git_commit)
    version = version.replace("{timestamp}", today.strftime("%Y%m%d") + "0000")
    return version


def _resolve_semver_release(schema: SchemaConfig, last_version: str | None) -> str:
    """Resolve semver release: parse last tag, apply auto_increment."""
    if last_version is None:
        major, minor, patch = 0, 0, 1
    else:
        major, minor, patch = parse_semver(last_version)
        component = schema.auto_increment or "patch"
        major, minor, patch = increment_semver(major, minor, patch, component)

    template = schema.release
    version = template.replace("{major}", str(major))
    version = version.replace("{minor}", str(minor))
    version = version.replace("{patch}", str(patch))
    return version


def _resolve_calver_release(template: str, last_version: str | None, today: datetime.date) -> str:
    """Resolve calver release: use today's date, error on conflict."""
    version = template.replace("{YYYY}", str(today.year))
    version = version.replace("{MM}", f"{today.month:02d}")
    version = version.replace("{DD}", f"{today.day:02d}")

    if last_version is not None and last_version == version:
        raise ValueError(
            f"CalVer conflict: version {version} already exists. Use --version to specify an explicit version."
        )
    return version


def _resolve_gitdate_release(template: str, git_count: int, today: datetime.date) -> str:
    """Resolve gitdate release: date + git_count (always unique)."""
    version = template.replace("{YYYY}", str(today.year))
    version = version.replace("{MM}", f"{today.month:02d}")
    version = version.replace("{DD}", f"{today.day:02d}")
    version = version.replace("{git_count}", str(git_count))
    return version
