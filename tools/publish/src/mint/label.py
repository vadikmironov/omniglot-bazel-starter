"""Bazel label utilities for mint."""

import re

_LABEL_RE = re.compile(r"^//[a-zA-Z0-9_/.-]+$")


def label_to_component_id(label: str) -> str:
    """Convert a Bazel label to a component ID for git tags.

    Takes the last path segment and replaces underscores with hyphens.
    Example: //modules/cpp_library -> cpp-library
    """
    if not _LABEL_RE.match(label):
        raise ValueError(f"Invalid Bazel label: {label}")
    last_segment = label.rstrip("/").rsplit("/", 1)[-1]
    return last_segment.replace("_", "-")


def label_to_publish_target(label: str) -> str:
    """Append :publish to a Bazel package label.

    Example: //modules/cpp_library -> //modules/cpp_library:publish
    """
    if not _LABEL_RE.match(label):
        raise ValueError(f"Invalid Bazel label: {label}")
    return f"{label}:publish"


def label_to_image_publish_target(label: str) -> str:
    """Append :publish_image to a Bazel package label.

    Example: //modules/java_app -> //modules/java_app:publish_image

    The target may not exist — gazelle emits :publish_image only for
    binary kinds that have a configured base in .publish.toml's
    [image_bases]. Callers should test existence (e.g., via bazel query)
    before invoking it.
    """
    if not _LABEL_RE.match(label):
        raise ValueError(f"Invalid Bazel label: {label}")
    return f"{label}:publish_image"
