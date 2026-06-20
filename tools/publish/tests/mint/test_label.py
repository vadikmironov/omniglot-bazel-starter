"""Tests for mint.label module."""

import unittest

from mint.label import (
    label_to_component_id,
    label_to_image_publish_target,
    label_to_publish_target,
)


class TestLabelToComponentId(unittest.TestCase):
    def test_simple_module(self):
        self.assertEqual(label_to_component_id("//modules/cpp_library"), "cpp-library")

    def test_hyphens_preserved(self):
        self.assertEqual(label_to_component_id("//modules/rust-app"), "rust-app")

    def test_nested_path(self):
        self.assertEqual(label_to_component_id("//some/deep/path/my_module"), "my-module")

    def test_no_underscores(self):
        self.assertEqual(label_to_component_id("//modules/goapp"), "goapp")

    def test_invalid_label_no_prefix(self):
        with self.assertRaises(ValueError):
            label_to_component_id("modules/foo")

    def test_invalid_label_empty(self):
        with self.assertRaises(ValueError):
            label_to_component_id("")


class TestLabelToPublishTarget(unittest.TestCase):
    def test_appends_publish(self):
        self.assertEqual(
            label_to_publish_target("//modules/java_lib"),
            "//modules/java_lib:publish",
        )

    def test_invalid_label(self):
        with self.assertRaises(ValueError):
            label_to_publish_target("not/a/label")


class TestLabelToImagePublishTarget(unittest.TestCase):
    def test_appends_publish_image(self):
        self.assertEqual(
            label_to_image_publish_target("//modules/java_app"),
            "//modules/java_app:publish_image",
        )

    def test_invalid_label(self):
        with self.assertRaises(ValueError):
            label_to_image_publish_target("not/a/label")


if __name__ == "__main__":
    unittest.main()
