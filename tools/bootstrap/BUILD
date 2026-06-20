load("@rules_python//python:defs.bzl", "py_binary", "py_library")
load("//tools/lint:linters.bzl", "ruff_test")

py_library(
    name = "bootstrap_lib",
    srcs = glob(
        ["src/**/*.py"],
        exclude = [
            "src/bootstrap/__main__.py",
            "src/bootstrap/cli.py",
        ],
    ),
    data = ["bootstrap_manifest.toml"],
    imports = ["src"],
    visibility = ["//tools/bootstrap:__subpackages__"],
)

py_binary(
    name = "bootstrap",
    srcs = [
        "src/bootstrap/__main__.py",
        "src/bootstrap/cli.py",
    ],
    imports = ["src"],
    main = "src/bootstrap/__main__.py",
    deps = [
        ":bootstrap_lib",
        "@omniglot-bazel-starter_pip_dependencies//questionary",
    ],
)

ruff_test(
    name = "bootstrap_lib.lint",
    size = "small",
    srcs = [":bootstrap_lib"],
    tags = ["lint"],
)

ruff_test(
    name = "bootstrap.lint",
    size = "small",
    srcs = [":bootstrap"],
    tags = ["lint"],
)
