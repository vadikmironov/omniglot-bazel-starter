"""Merging a repo's go.mod, go.sum and go_deps use_repo into the starter's."""

import unittest

from bootstrap.gomod import gover_key, merge_go_mod, merge_go_sum, merge_go_use_repo, semver_key

STARTER = """\
module example

go 1.26.0

require (
	github.com/bazelbuild/bazel-gazelle v0.54.0
	github.com/stretchr/testify v1.12.1
)

require golang.org/x/mod v0.23.0 // indirect
"""

# What the starter could ship under some other selection (a feature's module).
SHIPPABLE = STARTER + "\nrequire github.com/google/pprof v0.0.0-20261016150608-1facf8f91b50\n"


def _merge(repo: str) -> str:
    return merge_go_mod(STARTER, repo, SHIPPABLE)


class TestVersionOrder(unittest.TestCase):
    def test_semver_order(self) -> None:
        ordered = [
            "v0.0.0-20250101000000-aaaaaaaaaaaa",  # pseudo-versions are prereleases
            "v0.0.0-20260101000000-bbbbbbbbbbbb",
            "v0.1.0-rc.1",
            "v0.1.0-rc.2",
            "v0.1.0-rc.10",  # numeric identifiers compare as numbers
            "v0.1.0",
            "v0.1.1-0.20260101000000-cccccccccccc",
            "v0.1.1",
            "v1.9.0",
            "v1.10.0",
            "v2.0.0+incompatible",
        ]
        keys = [semver_key(v) for v in ordered]
        self.assertNotIn(None, keys)
        self.assertEqual(sorted(ordered, key=semver_key), ordered)

    def test_semver_ignores_build_metadata(self) -> None:
        self.assertEqual(semver_key("v2.0.0+incompatible"), semver_key("v2.0.0"))

    def test_not_a_semver(self) -> None:
        self.assertIsNone(semver_key("latest"))
        self.assertIsNone(semver_key("1.2.3"))

    def test_gover_order(self) -> None:
        ordered = ["1.20", "1.21", "1.21rc1", "1.21.0", "1.21.3", "1.26.0", "go1.26.1"]
        self.assertEqual(sorted(ordered, key=gover_key), ordered)
        self.assertEqual(gover_key("go1.26.1-custom"), gover_key("1.26.1"))


class TestMergeGoMod(unittest.TestCase):
    def test_unedited_repo_gets_the_starter_unchanged(self) -> None:
        self.assertEqual(_merge(STARTER), STARTER)

    def test_repo_only_requirements_are_added(self) -> None:
        repo = STARTER.replace(
            "require (\n",
            "require (\n\tgithub.com/google/uuid v1.6.0\n\tgolang.org/x/text v0.20.0 // indirect\n",
        )
        merged = _merge(repo)
        self.assertTrue(merged.startswith(STARTER.rstrip("\n")), "the starter's lines must come first, unchanged")
        self.assertIn(
            "\nrequire (\n\tgithub.com/google/uuid v1.6.0\n\tgolang.org/x/text v0.20.0 // indirect\n)\n", merged
        )

    def test_shared_requirement_takes_the_higher_version(self) -> None:
        newer = _merge(STARTER.replace("testify v1.12.1", "testify v1.13.0"))
        self.assertIn("\tgithub.com/stretchr/testify v1.13.0\n", newer)
        older = _merge(STARTER.replace("testify v1.12.1", "testify v1.11.0"))
        self.assertIn("\tgithub.com/stretchr/testify v1.12.1\n", older)

    def test_direct_use_wins_over_indirect(self) -> None:
        merged = _merge(STARTER.replace("golang.org/x/mod v0.23.0 // indirect", "golang.org/x/mod v0.23.0"))
        self.assertIn("\nrequire golang.org/x/mod v0.23.0\n", merged)

    def test_go_directive_takes_the_higher_version(self) -> None:
        self.assertIn("\ngo 1.27.0\n", _merge(STARTER.replace("go 1.26.0", "go 1.27.0")))
        self.assertIn("\ngo 1.26.0\n", _merge(STARTER.replace("go 1.26.0", "go 1.25")))

    def test_repo_module_path_is_kept(self) -> None:
        merged = _merge(STARTER.replace("module example", "module github.com/me/example"))
        self.assertTrue(merged.startswith("module github.com/me/example\n"))

    def test_repo_directives_are_added(self) -> None:
        repo = STARTER + "\nreplace github.com/google/uuid => ../uuid\n\ntool golang.org/x/tools/cmd/stringer\n"
        merged = _merge(repo)
        self.assertIn("\nreplace github.com/google/uuid => ../uuid\n", merged)
        self.assertIn("\ntool golang.org/x/tools/cmd/stringer\n", merged)

    def test_a_module_the_starter_could_ship_is_left_to_the_selection(self) -> None:
        # pprof belongs to a feature this selection does not have.
        repo = STARTER + "\nrequire github.com/google/pprof v0.0.0-20261016150608-1facf8f91b50\n"
        self.assertNotIn("google/pprof", _merge(repo))

    def test_merge_is_idempotent(self) -> None:
        repo = STARTER.replace("testify v1.12.1", "testify v1.13.0") + (
            "\nrequire (\n\tgithub.com/google/uuid v1.6.0\n\tgolang.org/x/text v0.20.0 // indirect\n)\n"
            "\nreplace github.com/google/uuid => ../uuid\n"
        )
        once = _merge(repo)
        self.assertEqual(_merge(once), once)


class TestMergeGoSum(unittest.TestCase):
    def test_union_in_go_order(self) -> None:
        starter = "b.io/m v1.10.0 h1:B10=\nb.io/m v1.10.0/go.mod h1:B10mod=\n"
        repo = "a.io/x v1.0.0 h1:A=\nb.io/m v1.9.0 h1:B9=\nb.io/m v1.10.0 h1:B10=\n"
        self.assertEqual(
            merge_go_sum(starter, repo),
            "a.io/x v1.0.0 h1:A=\nb.io/m v1.9.0 h1:B9=\nb.io/m v1.10.0 h1:B10=\nb.io/m v1.10.0/go.mod h1:B10mod=\n",
        )


class TestMergeGoUseRepo(unittest.TestCase):
    SEGMENT = 'go_deps = use_extension("@gazelle//:extensions.bzl", "go_deps")\nuse_repo(\n    go_deps,\n    "com_github_stretchr_testify",\n)\n'

    def test_repo_names_join_the_first_call(self) -> None:
        repo = self.SEGMENT.replace(
            '"com_github_stretchr_testify",', '"com_github_stretchr_testify",\n    "com_github_google_uuid",'
        )
        merged = merge_go_use_repo(self.SEGMENT, repo, self.SEGMENT)
        self.assertIn('    "com_github_stretchr_testify",\n    "com_github_google_uuid",\n)', merged)
        self.assertEqual(merge_go_use_repo(self.SEGMENT, merged, self.SEGMENT), merged)

    def test_a_repo_the_starter_could_ship_is_left_to_the_selection(self) -> None:
        shippable = self.SEGMENT + 'use_repo(go_deps, "com_github_google_pprof")\n'
        repo = shippable
        self.assertEqual(merge_go_use_repo(self.SEGMENT, repo, shippable), self.SEGMENT)


if __name__ == "__main__":
    unittest.main()
