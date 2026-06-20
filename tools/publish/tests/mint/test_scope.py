"""Tests for mint.scope module."""

import unittest

from mint.config import ComponentSetConfig, PublishConfig, SchemaConfig
from mint.scope import group_by_version_scope, resolve_scope

MINIMAL_SCHEMA = SchemaConfig(
    release="{major}.{minor}.{patch}",
    development="{next_version}",
)


def _make_config(
    component_sets: dict | None = None,
    independent: list | None = None,
) -> PublishConfig:
    sets = {}
    if component_sets:
        for name, modules in component_sets.items():
            sets[name] = ComponentSetConfig(modules=modules)
    return PublishConfig(
        schema="{s}",
        schemas={"s": MINIMAL_SCHEMA},
        component_sets=sets,
        independent=independent or [],
    )


class TestResolveScope(unittest.TestCase):
    def test_none_returns_all(self):
        config = _make_config(
            component_sets={"backend": ["//modules/a", "//modules/b"]},
            independent=["//modules/c"],
        )
        result = resolve_scope(config, None)
        self.assertEqual(sorted(result), ["//modules/a", "//modules/b", "//modules/c"])

    def test_component_set_name(self):
        config = _make_config(
            component_sets={"backend": ["//modules/a", "//modules/b"]},
        )
        result = resolve_scope(config, "backend")
        self.assertEqual(result, ["//modules/a", "//modules/b"])

    def test_single_label(self):
        config = _make_config()
        result = resolve_scope(config, "//modules/foo")
        self.assertEqual(result, ["//modules/foo"])

    def test_unknown_set_raises(self):
        config = _make_config(
            component_sets={"backend": ["//modules/a"]},
        )
        with self.assertRaises(ValueError, msg="Unknown scope"):
            resolve_scope(config, "frontend")

    def test_none_with_empty_config(self):
        config = _make_config()
        result = resolve_scope(config, None)
        self.assertEqual(result, [])


class TestGroupByVersionScope(unittest.TestCase):
    def test_mixed_scopes(self):
        config = _make_config(
            component_sets={"backend": ["//modules/a", "//modules/b"]},
            independent=["//modules/c"],
        )
        modules = ["//modules/a", "//modules/b", "//modules/c", "//modules/d"]
        groups = group_by_version_scope(config, modules)

        # Should produce 3 groups: repo-wide (d), set (backend), independent (c)
        self.assertEqual(len(groups), 3)

        prefixes = {g.tag_prefix: g.modules for g in groups}
        self.assertEqual(prefixes[""], ["//modules/d"])
        self.assertEqual(prefixes["backend/"], ["//modules/a", "//modules/b"])
        self.assertEqual(prefixes["c/"], ["//modules/c"])

    def test_only_repo_wide(self):
        config = _make_config()
        groups = group_by_version_scope(config, ["//modules/x"])
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].tag_prefix, "")
        self.assertEqual(groups[0].modules, ["//modules/x"])

    def test_only_component_set(self):
        config = _make_config(
            component_sets={"java_all": ["//modules/j1", "//modules/j2"]},
        )
        groups = group_by_version_scope(config, ["//modules/j1", "//modules/j2"])
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].tag_prefix, "java_all/")

    def test_empty_modules(self):
        config = _make_config()
        groups = group_by_version_scope(config, [])
        self.assertEqual(groups, [])

    def test_independent_component_id(self):
        config = _make_config(independent=["//modules/cpp_library"])
        groups = group_by_version_scope(config, ["//modules/cpp_library"])
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].tag_prefix, "cpp-library/")


if __name__ == "__main__":
    unittest.main()
