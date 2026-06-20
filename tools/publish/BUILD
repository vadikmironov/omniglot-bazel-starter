# --- BEGIN feature:lint ---
# The lint tests below are gazelle-generated (bazel run //:lint_gen) but wrapped
# in feature:lint section markers so they drop out of non-lint scaffolds.
# gazelle:lint_ignore_keep freezes this package — lint_gen neither regenerates nor
# prunes here — so a repo-wide run won't disturb the gating. To refresh them,
# delete the directive line, run lint_gen, re-wrap the emitted rules in feature:lint
# markers, then restore this line.
# gazelle:lint_ignore_keep
# --- END feature:lint ---

load("@bazel_skylib//rules:common_settings.bzl", "string_flag")
load("@rules_python//python:defs.bzl", "py_binary", "py_library")

# --- BEGIN feature:lint ---
load("//tools/lint:linters.bzl", "ruff_test")
# --- END feature:lint ---

load("//tools/publish:publish_config.bzl", "publish_config")

exports_files(
    [
        "publish_artifact.sh",
        "credential-helper",
        "docker_login_helper.py",
        "netrc_lib.sh",
        "repackage_wheel.py",
    ],
    visibility = ["//visibility:public"],
)

# Publish configuration flags — set via .bazelrc (--config=publish) or user.bazelrc.
# Env vars of the same name (without _DEFAULT suffix) override at runtime.

string_flag(
    name = "url",
    build_setting_default = "",
    visibility = ["//visibility:public"],
)

# Image-publish base URL — typically a different hostname/path from `url`
# (Artifactory's Docker registry endpoint differs from its REST API).
string_flag(
    name = "docker_url",
    build_setting_default = "",
    visibility = ["//visibility:public"],
)

string_flag(
    name = "platform",
    build_setting_default = "artifactory",
    visibility = ["//visibility:public"],
)

string_flag(
    name = "owner",
    build_setting_default = "",
    visibility = ["//visibility:public"],
)

# Per-mode repository name flags — team defaults for artifact repos.
# Maven uses separate repos for releases and snapshots (standard Maven convention).
# Override per-developer in user.bazelrc or at runtime via env vars
# (PUBLISH_MAVEN_RELEASE_REPO, PUBLISH_MAVEN_SNAPSHOT_REPO, PUBLISH_PYPI_REPO,
#  PUBLISH_GENERIC_REPO).
# No defaults — if not configured, publish targets fail with a helpful message.

string_flag(
    name = "maven_release_repo",
    build_setting_default = "",
    visibility = ["//visibility:public"],
)

string_flag(
    name = "maven_snapshot_repo",
    build_setting_default = "",
    visibility = ["//visibility:public"],
)

string_flag(
    name = "pypi_repo",
    build_setting_default = "",
    visibility = ["//visibility:public"],
)

string_flag(
    name = "generic_repo",
    build_setting_default = "",
    visibility = ["//visibility:public"],
)

# Image-publish repository — single repo (not split into snapshot/release).
# Snapshot/release discrimination happens via PUBLISH_VERSION's tag suffix.
string_flag(
    name = "docker_repo",
    build_setting_default = "",
    visibility = ["//visibility:public"],
)

publish_config(
    name = "publish_config",
    visibility = ["//visibility:public"],
)

# =========================================================================
# mint — publish orchestrator
# =========================================================================

py_library(
    name = "mint_lib",
    srcs = glob(
        ["src/**/*.py"],
        exclude = [
            "src/mint/__main__.py",
            "src/mint/cli.py",
        ],
    ),
    imports = ["src"],
    visibility = ["//tools/publish:__subpackages__"],
)

py_binary(
    name = "mint",
    srcs = [
        "src/mint/__main__.py",
        "src/mint/cli.py",
    ],
    data = ["//:.publish.toml"],
    imports = ["src"],
    main = "src/mint/__main__.py",
    deps = [":mint_lib"],
)

# --- BEGIN feature:lint ---
ruff_test(
    name = "mint_lib.lint",
    size = "small",
    srcs = [":mint_lib"],
    tags = ["lint"],
)

ruff_test(
    name = "mint.lint",
    size = "small",
    srcs = [":mint"],
    tags = ["lint"],
)
# --- END feature:lint ---

# =========================================================================
# docker-login-helper — populates ~/.docker/config.json for image_publish
# =========================================================================

py_binary(
    name = "docker_login_helper",
    srcs = ["docker_login_helper.py"],
    visibility = ["//visibility:public"],
)

# --- BEGIN feature:lint ---
ruff_test(
    name = "docker_login_helper.lint",
    size = "small",
    srcs = [":docker_login_helper"],
    tags = ["lint"],
)
# --- END feature:lint ---
