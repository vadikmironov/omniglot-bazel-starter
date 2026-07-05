load("@rules_python//python:defs.bzl", "py_library", "py_test")
load("//tools/lint:linters.bzl", "ruff_test", "ty_test")
load("//tools/publish/lang:python_publish_defs.bzl", "python_publish")

package(default_visibility = ["//visibility:public"])

python_publish(
    name = "publish",
    distribution = "omniglot-bazel-starter-python-lib",
    library_target = ":python_lib",
)

py_library(
    name = "python_lib",
    srcs = glob(["src/**/*.py"]),
    imports = ["src"],
)

py_test(
    name = "python_lib_test",
    timeout = "short",
    srcs = glob(["tests/test_hello_world_function/**/*.py"]),
    main = "tests/test_hello_world_function/test_hello_world_lib.py",
    deps = ["//modules/python_lib"],
)

ruff_test(
    name = "python_lib.lint",
    size = "small",
    srcs = [":python_lib"],
    tags = ["lint"],
)

ty_test(
    name = "python_lib.ty",
    size = "small",
    srcs = [":python_lib"],
    tags = ["lint"],
)
