"""Tests for mint.version module."""

import datetime
import unittest

from mint.config import SchemaConfig
from mint.version import (
    increment_semver,
    parse_semver,
    resolve_dev_version,
    resolve_release_version,
)

SEMVER = SchemaConfig(
    release="{major}.{minor}.{patch}",
    development="{next_version}.dev{git_count}+{git_commit}",
    auto_increment="patch",
)

SEMVER_MINOR = SchemaConfig(
    release="{major}.{minor}.{patch}",
    development="{next_version}.dev{git_count}+{git_commit}",
    auto_increment="minor",
)

SEMVER_MAJOR = SchemaConfig(
    release="{major}.{minor}.{patch}",
    development="{next_version}.dev{git_count}+{git_commit}",
    auto_increment="major",
)

CALVER = SchemaConfig(
    release="{YYYY}.{MM}.{DD}",
    development="{next_version}.dev{git_count}+{git_commit}",
)

GITDATE = SchemaConfig(
    release="{YYYY}.{MM}.{DD}.{git_count}",
    development="{next_version}+{git_commit}",
)

FIXED_DATE = datetime.date(2026, 4, 7)


class TestParseSemver(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(parse_semver("1.2.3"), (1, 2, 3))

    def test_with_prerelease(self):
        self.assertEqual(parse_semver("1.2.3-beta.1"), (1, 2, 3))

    def test_with_build_metadata(self):
        self.assertEqual(parse_semver("1.2.3+abc1234"), (1, 2, 3))

    def test_zero(self):
        self.assertEqual(parse_semver("0.0.0"), (0, 0, 0))

    def test_invalid(self):
        with self.assertRaises(ValueError):
            parse_semver("not-a-version")


class TestIncrementSemver(unittest.TestCase):
    def test_patch(self):
        self.assertEqual(increment_semver(1, 2, 3, "patch"), (1, 2, 4))

    def test_minor(self):
        self.assertEqual(increment_semver(1, 2, 3, "minor"), (1, 3, 0))

    def test_major(self):
        self.assertEqual(increment_semver(1, 2, 3, "major"), (2, 0, 0))

    def test_invalid_component(self):
        with self.assertRaises(ValueError):
            increment_semver(1, 2, 3, "build")


class TestResolveReleaseVersion(unittest.TestCase):
    # Semver
    def test_semver_increment_patch(self):
        result = resolve_release_version(SEMVER, "1.2.3")
        self.assertEqual(result, "1.2.4")

    def test_semver_increment_minor(self):
        result = resolve_release_version(SEMVER_MINOR, "1.2.3")
        self.assertEqual(result, "1.3.0")

    def test_semver_increment_major(self):
        result = resolve_release_version(SEMVER_MAJOR, "1.2.3")
        self.assertEqual(result, "2.0.0")

    def test_semver_no_prior_tag(self):
        result = resolve_release_version(SEMVER, None)
        self.assertEqual(result, "0.0.1")

    # Calver
    def test_calver_today(self):
        result = resolve_release_version(CALVER, None, now=FIXED_DATE)
        self.assertEqual(result, "2026.04.07")

    def test_calver_conflict(self):
        with self.assertRaises(ValueError, msg="conflict"):
            resolve_release_version(CALVER, "2026.04.07", now=FIXED_DATE)

    def test_calver_no_conflict_different_day(self):
        result = resolve_release_version(CALVER, "2026.04.06", now=FIXED_DATE)
        self.assertEqual(result, "2026.04.07")

    # Gitdate
    def test_gitdate(self):
        result = resolve_release_version(GITDATE, None, git_count=42, now=FIXED_DATE)
        self.assertEqual(result, "2026.04.07.42")

    def test_gitdate_zero_commits(self):
        result = resolve_release_version(GITDATE, None, git_count=0, now=FIXED_DATE)
        self.assertEqual(result, "2026.04.07.0")


class TestResolveDevVersion(unittest.TestCase):
    def test_semver_dev(self):
        result = resolve_dev_version(SEMVER, "1.2.4", 7, "abc1234")
        self.assertEqual(result, "1.2.4.dev7+abc1234")

    def test_calver_dev(self):
        result = resolve_dev_version(CALVER, "2026.04.07", 3, "def5678")
        self.assertEqual(result, "2026.04.07.dev3+def5678")

    def test_gitdate_dev(self):
        result = resolve_dev_version(GITDATE, "2026.04.07.42", 42, "abc1234")
        self.assertEqual(result, "2026.04.07.42+abc1234")

    def test_zero_commits(self):
        result = resolve_dev_version(SEMVER, "1.0.0", 0, "abc1234")
        self.assertEqual(result, "1.0.0.dev0+abc1234")


if __name__ == "__main__":
    unittest.main()
