"""Tests for mint.config module."""

import tempfile
import unittest
from pathlib import Path

from mint.config import load_config


class TestLoadConfig(unittest.TestCase):
    def _write_toml(self, content: str) -> Path:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(content)
        return Path(f.name)

    def test_valid_config(self):
        path = self._write_toml("""\
[repo]
schema = "{semver}"

[schemas.semver]
release = "{major}.{minor}.{patch}"
development = "{next_version}.dev{git_count}+{git_commit}"
auto_increment = "patch"

[component_sets.backend]
modules = ["//modules/java_lib", "//modules/java_app"]

[components]
independent = ["//modules/cpp_library"]
""")
        config = load_config(path)
        self.assertEqual(config.schema, "{semver}")
        self.assertIn("semver", config.schemas)
        self.assertEqual(config.schemas["semver"].auto_increment, "patch")
        self.assertEqual(len(config.component_sets["backend"].modules), 2)
        self.assertEqual(config.independent, ["//modules/cpp_library"])

    def test_resolve_schema(self):
        path = self._write_toml("""\
[repo]
schema = "{semver}"

[schemas.semver]
release = "{major}.{minor}.{patch}"
development = "{next_version}.dev{git_count}+{git_commit}"
auto_increment = "minor"
""")
        config = load_config(path)
        name, schema = config.resolve_schema()
        self.assertEqual(name, "semver")
        self.assertEqual(schema.auto_increment, "minor")

    def test_format_version_passthrough(self):
        path = self._write_toml("""\
[repo]
schema = "{semver}"

[schemas.semver]
release = "{major}.{minor}.{patch}"
development = "{next_version}.dev{git_count}+{git_commit}"
""")
        config = load_config(path)
        self.assertEqual(config.format_version("1.2.3"), "1.2.3")

    def test_format_version_with_prefix(self):
        path = self._write_toml("""\
[repo]
schema = "my_monorepo_{semver}"

[schemas.semver]
release = "{major}.{minor}.{patch}"
development = "{next_version}.dev{git_count}+{git_commit}"
""")
        config = load_config(path)
        self.assertEqual(config.format_version("1.2.3"), "my_monorepo_1.2.3")

    def test_missing_repo_schema(self):
        path = self._write_toml("""\
[schemas.semver]
release = "{major}.{minor}.{patch}"
development = "{next_version}.dev{git_count}+{git_commit}"
""")
        with self.assertRaises(ValueError, msg="must define 'schema'"):
            load_config(path)

    def test_schema_reference_not_found(self):
        path = self._write_toml("""\
[repo]
schema = "{nonexistent}"

[schemas.semver]
release = "{major}.{minor}.{patch}"
development = "{next_version}.dev{git_count}+{git_commit}"
""")
        with self.assertRaises(ValueError, msg="not found"):
            load_config(path)

    def test_schema_missing_release(self):
        path = self._write_toml("""\
[repo]
schema = "{bad}"

[schemas.bad]
development = "{next_version}.dev{git_count}+{git_commit}"
""")
        with self.assertRaises(ValueError, msg="missing 'release'"):
            load_config(path)

    def test_schema_missing_development(self):
        path = self._write_toml("""\
[repo]
schema = "{bad}"

[schemas.bad]
release = "{major}.{minor}.{patch}"
""")
        with self.assertRaises(ValueError, msg="missing 'development'"):
            load_config(path)

    def test_invalid_auto_increment(self):
        path = self._write_toml("""\
[repo]
schema = "{s}"

[schemas.s]
release = "{major}.{minor}.{patch}"
development = "{next_version}"
auto_increment = "build"
""")
        with self.assertRaises(ValueError, msg="patch/minor/major"):
            load_config(path)

    def test_duplicate_module_across_sets(self):
        path = self._write_toml("""\
[repo]
schema = "{s}"

[schemas.s]
release = "{major}.{minor}.{patch}"
development = "{next_version}"

[component_sets.a]
modules = ["//modules/foo"]

[component_sets.b]
modules = ["//modules/foo"]
""")
        with self.assertRaises(ValueError, msg="appears in both"):
            load_config(path)

    def test_duplicate_module_set_and_independent(self):
        path = self._write_toml("""\
[repo]
schema = "{s}"

[schemas.s]
release = "{major}.{minor}.{patch}"
development = "{next_version}"

[component_sets.a]
modules = ["//modules/foo"]

[components]
independent = ["//modules/foo"]
""")
        with self.assertRaises(ValueError, msg="appears in both"):
            load_config(path)

    def test_invalid_label(self):
        path = self._write_toml("""\
[repo]
schema = "{s}"

[schemas.s]
release = "{major}.{minor}.{patch}"
development = "{next_version}"

[component_sets.a]
modules = ["modules/foo"]
""")
        with self.assertRaises(ValueError, msg="must start with '//'"):
            load_config(path)

    def test_empty_component_set(self):
        path = self._write_toml("""\
[repo]
schema = "{s}"

[schemas.s]
release = "{major}.{minor}.{patch}"
development = "{next_version}"

[component_sets.empty]
modules = []
""")
        with self.assertRaises(ValueError, msg="has no modules"):
            load_config(path)

    def test_all_modules(self):
        path = self._write_toml("""\
[repo]
schema = "{s}"

[schemas.s]
release = "{major}.{minor}.{patch}"
development = "{next_version}"

[component_sets.a]
modules = ["//modules/x", "//modules/y"]

[components]
independent = ["//modules/z"]
""")
        config = load_config(path)
        self.assertEqual(
            sorted(config.all_modules()),
            ["//modules/x", "//modules/y", "//modules/z"],
        )

    def test_no_component_sets_or_independent(self):
        path = self._write_toml("""\
[repo]
schema = "{s}"

[schemas.s]
release = "{major}.{minor}.{patch}"
development = "{next_version}"
""")
        config = load_config(path)
        self.assertEqual(config.all_modules(), [])
        self.assertEqual(config.component_sets, {})
        self.assertEqual(config.independent, [])


if __name__ == "__main__":
    unittest.main()
