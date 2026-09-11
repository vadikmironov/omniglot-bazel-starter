load("@rules_python//python:defs.bzl", "py_test")

# The suites tagged `external` read the live source tree (manifest, composite
# files, whole tool directories) through their resolved __file__ path, not
# through declared inputs, so a cached result can outlive the tree it judged.
# The tag makes Bazel run them every time, locally and in CI.

py_test(
    name = "test_processor",
    size = "small",
    srcs = ["test_processor.py"],
    deps = ["//tools/bootstrap:bootstrap_lib"],
)

py_test(
    name = "test_manifest",
    size = "small",
    srcs = ["test_manifest.py"],
    tags = ["external"],
    deps = ["//tools/bootstrap:bootstrap_lib"],
)

py_test(
    name = "test_scaffolder",
    size = "small",
    srcs = ["test_scaffolder.py"],
    local = True,
    tags = ["external"],
    deps = ["//tools/bootstrap:bootstrap_lib"],
)

py_test(
    name = "test_regression",
    size = "small",
    srcs = ["test_regression.py"],
    local = True,
    tags = ["external"],
    deps = ["//tools/bootstrap:bootstrap_lib"],
)

py_test(
    name = "test_rebootstrap",
    size = "small",
    srcs = ["test_rebootstrap.py"],
    local = True,
    tags = ["external"],
    deps = ["//tools/bootstrap:bootstrap_lib"],
)

py_test(
    name = "test_integration",
    size = "enormous",
    timeout = "eternal",
    srcs = ["test_integration.py"],
    local = True,
    tags = [
        "external",
        "manual",
    ],
    deps = ["//tools/bootstrap:bootstrap_lib"],
)
