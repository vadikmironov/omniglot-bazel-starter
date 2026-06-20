"""Publish macros for binary bundles and library archives.

Used for application binaries and libraries in all languages (C++, Rust, Go,
Python apps). Packages artifacts into zip archives and publishes to Maven
coordinates.
"""

load("@rules_pkg//pkg:zip.bzl", "pkg_zip")
load(
    "//tools/publish:publish_defs.bzl",
    "DEFAULT_MAVEN_GROUP",
    "artifactory_upload",
)

def binary_bundle_publish(
        name,
        binary_target,
        artifact_id,
        group_id = DEFAULT_MAVEN_GROUP,
        repo_name = None,
        extra_files = [],
        classifier = "",
        visibility = None):
    """Zips a binary (with optional extra files) and publishes to Maven coordinates.

    Used for application binaries in all languages (C++, Rust, Go, Python apps).

    Args:
        name: Target name (conventionally "publish").
        binary_target: Label of the binary target to package.
        artifact_id: Maven artifact ID (e.g., "cpp-app").
        group_id: Maven group ID.
        repo_name: Repository name override. If None, PUBLISH_MODE selects
            maven_release_repo or maven_snapshot_repo, falling back to
            generic_repo. Fails if nothing is configured.
        extra_files: Additional files to include in the zip archive.
        classifier: Maven classifier (e.g., "linux-x86_64"), empty if none.
        visibility: Bazel visibility.
    """
    zip_name = "_" + name + "_zip"
    pkg_zip(
        name = zip_name,
        srcs = [binary_target] + extra_files,
        visibility = ["//visibility:private"],
    )

    pkg = native.package_name()
    artifact_path = "_main/" + pkg + "/" + zip_name + ".zip"

    artifactory_upload(
        name = name,
        artifact = ":" + zip_name,
        artifact_runfiles_path = artifact_path,
        mode = "maven",
        repo_name = repo_name,
        artifact_id = artifact_id,
        group_id = group_id,
        classifier = classifier,
        packaging = "zip",
        visibility = visibility,
    )

def library_archive_publish(
        name,
        library_target,
        artifact_id,
        group_id = DEFAULT_MAVEN_GROUP,
        repo_name = None,
        hdrs = [],
        classifier = "",
        visibility = None):
    """Zips a library (with optional headers) and publishes to Maven coordinates.

    Used for C++, Rust, and Go libraries. For C++ libraries, pass hdrs to include
    header files in the archive.

    Args:
        name: Target name (conventionally "publish").
        library_target: Label of the library target to package.
        artifact_id: Maven artifact ID (e.g., "cpp-library").
        group_id: Maven group ID.
        repo_name: Repository name override. If None, PUBLISH_MODE selects
            maven_release_repo or maven_snapshot_repo, falling back to
            generic_repo. Fails if nothing is configured.
        hdrs: Additional header/interface files to include in the archive.
        classifier: Maven classifier (e.g., "linux-x86_64"), empty if none.
        visibility: Bazel visibility.
    """
    zip_name = "_" + name + "_zip"
    pkg_zip(
        name = zip_name,
        srcs = [library_target] + hdrs,
        visibility = ["//visibility:private"],
    )

    pkg = native.package_name()
    artifact_path = "_main/" + pkg + "/" + zip_name + ".zip"

    artifactory_upload(
        name = name,
        artifact = ":" + zip_name,
        artifact_runfiles_path = artifact_path,
        mode = "maven",
        repo_name = repo_name,
        artifact_id = artifact_id,
        group_id = group_id,
        classifier = classifier,
        packaging = "zip",
        visibility = visibility,
    )
