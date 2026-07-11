# --- BEGIN feature:lint ---
# The lint tests below are gazelle-generated (bazel run //:lint_gen) but wrapped
# in feature:lint section markers so they drop out of non-lint scaffolds.
# gazelle:lint_ignore_keep freezes this package — lint_gen neither regenerates nor
# prunes here — so a repo-wide run won't disturb the gating. To refresh them,
# delete the directive line, run lint_gen, re-wrap the emitted rules in feature:lint
# markers, then restore this line.
# gazelle:lint_ignore_keep
# --- END feature:lint ---

load("@rules_python//python:defs.bzl", "py_binary", "py_library")

# --- BEGIN feature:lint ---
load("//tools/lint:linters.bzl", "ruff_test", "ty_test")
# --- END feature:lint ---

# =========================================================================
# profile — profiling runner (capture -> folded stacks -> flamegraph)
# =========================================================================

py_library(
    name = "profiling_lib",
    srcs = glob(
        ["src/**/*.py"],
        exclude = [
            "src/profiling/__main__.py",
            "src/profiling/cli.py",
        ],
    ),
    imports = ["src"],
    visibility = ["//tools/profile:__subpackages__"],
    deps = ["@rules_python//python/runfiles"],
)

py_binary(
    name = "profile",
    srcs = [
        "src/profiling/__main__.py",
        "src/profiling/cli.py",
    ],
    data = [
        "@com_github_felixge_pprofutils_v2//cmd/pprofutils",
        "@crates//:flamelens__flamelens",
        "@crates//:inferno__inferno-flamegraph",
    ],
    env = {
        "PROFILE_FLAMELENS": "$(rlocationpath @crates//:flamelens__flamelens)",
        "PROFILE_INFERNO": "$(rlocationpath @crates//:inferno__inferno-flamegraph)",
        "PROFILE_PPROFUTILS": "$(rlocationpath @com_github_felixge_pprofutils_v2//cmd/pprofutils)",
    },
    imports = ["src"],
    main = "src/profiling/__main__.py",
    deps = [":profiling_lib"],
)

# --- BEGIN feature:lint ---
ruff_test(
    name = "profiling_lib.lint",
    size = "small",
    srcs = [":profiling_lib"],
    tags = ["lint"],
)

ruff_test(
    name = "profile.lint",
    size = "small",
    srcs = [":profile"],
    tags = ["lint"],
)

ty_test(
    name = "profiling_lib.ty",
    size = "small",
    srcs = [":profiling_lib"],
    tags = ["lint"],
)

ty_test(
    name = "profile.ty",
    size = "small",
    srcs = [":profile"],
    tags = ["lint"],
)
# --- END feature:lint ---
