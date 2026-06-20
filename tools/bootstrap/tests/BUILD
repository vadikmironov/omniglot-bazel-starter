load("@rules_python//python:defs.bzl", "py_test")

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
    deps = ["//tools/bootstrap:bootstrap_lib"],
)

py_test(
    name = "test_scaffolder",
    size = "small",
    srcs = ["test_scaffolder.py"],
    local = True,
    deps = ["//tools/bootstrap:bootstrap_lib"],
)

py_test(
    name = "test_regression",
    size = "small",
    srcs = ["test_regression.py"],
    local = True,
    deps = ["//tools/bootstrap:bootstrap_lib"],
)

py_test(
    name = "test_rebootstrap",
    size = "small",
    srcs = ["test_rebootstrap.py"],
    local = True,
    deps = ["//tools/bootstrap:bootstrap_lib"],
)

py_test(
    name = "test_integration",
    size = "enormous",
    timeout = "eternal",
    srcs = ["test_integration.py"],
    local = True,
    tags = ["manual"],
    deps = ["//tools/bootstrap:bootstrap_lib"],
)
