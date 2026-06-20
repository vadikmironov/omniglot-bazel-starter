"""Publishes a Python library wheel to a PyPI repository.

Separated from core publish_defs.bzl to avoid a rules_python dependency
for non-Python repos.
"""

load("@rules_python//python:packaging.bzl", "py_wheel")
load(
    "//tools/publish:publish_defs.bzl",
    "artifactory_upload",
)

# Build-time placeholder — replaced by repackage_wheel.py at publish time
# with the actual PUBLISH_VERSION in metadata, dist-info dir, and filename.
_WHEEL_VERSION = "0.0.0"

def python_publish(
        name,
        library_target,
        distribution,
        repo_name = None,
        requires = [],
        python_tag = "py3",
        strip_path_prefixes = [],
        visibility = None):
    """Publishes a Python library wheel to a PyPI repository.

    Creates a py_wheel target from the library and an upload wrapper. The wheel
    is built with a placeholder version (0.0.0) and automatically repackaged
    at publish time with the actual PUBLISH_VERSION before upload.

    Args:
        name: Target name (conventionally "publish").
        library_target: Label of the py_library target.
        distribution: PyPI distribution/package name (e.g., "omniglot-bazel-starter-python-lib").
        repo_name: Repository name override. If None, resolved at runtime
            from pypi_repo flag, falling back to generic_repo. Fails if
            nothing is configured.
        requires: List of PyPI dependency strings for wheel metadata.
        python_tag: Python compatibility tag (default: "py3").
        strip_path_prefixes: Path prefixes to strip from wheel file paths.
        visibility: Bazel visibility.
    """
    wheel_name = "_" + name + "_wheel"

    # Distribution name in wheel filename uses underscores per PEP 427
    wheel_distribution = distribution.replace("-", "_")
    wheel_filename = wheel_distribution + "-" + _WHEEL_VERSION + "-" + python_tag + "-none-any.whl"

    py_wheel(
        name = wheel_name,
        distribution = wheel_distribution,
        version = _WHEEL_VERSION,
        python_tag = python_tag,
        requires = requires,
        strip_path_prefixes = strip_path_prefixes,
        deps = [library_target],
        visibility = ["//visibility:private"],
    )

    pkg = native.package_name()
    artifact_path = "_main/" + pkg + "/" + wheel_filename

    artifactory_upload(
        name = name,
        artifact = ":" + wheel_name,
        artifact_runfiles_path = artifact_path,
        mode = "pypi",
        repo_name = repo_name,
        artifact_id = wheel_distribution,
        packaging = "whl",
        visibility = visibility,
    )
