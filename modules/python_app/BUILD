load("@rules_python//python:defs.bzl", "py_binary", "py_library")
load("//tools/lint:linters.bzl", "ruff_test")
load("//tools/publish/lang:generic_publish_defs.bzl", "binary_bundle_publish")
load("//tools/publish/lang:image_publish_defs.bzl", "image_publish")

package(default_visibility = ["//visibility:public"])

binary_bundle_publish(
    name = "publish",
    artifact_id = "python-app",
    binary_target = ":python_app",
)

py_library(
    name = "python_app_lib",
    srcs = glob(
        ["src/**/*.py"],
        exclude = ["src/**/__main__.py"],
    ),
    imports = ["src"],
    deps = ["//modules/python_lib"],
)

py_binary(
    name = "python_app",
    srcs = glob(["src/**/__main__.py"]),
    main = "__main__.py",
    # please see https://github.com/theoremlp/rules_mypy?tab=readme-ov-file#skipping-targets for more information
    #tags = ["no-mypy"],
    deps = ["//modules/python_app:python_app_lib"],
)

ruff_test(
    name = "python_app_lib.lint",
    size = "small",
    srcs = [":python_app_lib"],
    tags = ["lint"],
)

ruff_test(
    name = "python_app.lint",
    size = "small",
    srcs = [":python_app"],
    tags = ["lint"],
)

image_publish(
    name = "publish_image",
    app_prefix = "app",
    artifact_id = "python-app",
    base = "@gcr_io_distroless_python3",
    binary_target = ":python_app",
    entrypoint = ["/app/python_app"],
    strip_prefix = "modules/python_app",
)
