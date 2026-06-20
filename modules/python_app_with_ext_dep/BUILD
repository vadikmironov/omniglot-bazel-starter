load("@omniglot-bazel-starter_pip_dependencies//:requirements.bzl", "requirement")
load("@rules_python//python:defs.bzl", "py_binary", "py_library")
load("//tools/lint:linters.bzl", "ruff_test")
load("//tools/publish/lang:generic_publish_defs.bzl", "binary_bundle_publish")
load("//tools/publish/lang:image_publish_defs.bzl", "image_publish")

package(default_visibility = ["//visibility:public"])

binary_bundle_publish(
    name = "publish",
    artifact_id = "python-app-with-ext-dep",
    binary_target = ":python_app_with_ext_dep",
)

py_library(
    name = "python_app_with_ext_dep_lib",
    srcs = glob(
        ["src/**/*.py"],
        exclude = ["src/**/__main__.py"],
    ),
    imports = ["src"],
    # dependency on an external PyPI package
    deps = [requirement("requests")],
)

py_binary(
    name = "python_app_with_ext_dep",
    srcs = glob(["src/**/__main__.py"]),
    main = "__main__.py",
    deps = ["//modules/python_app_with_ext_dep:python_app_with_ext_dep_lib"],
)

ruff_test(
    name = "python_app_with_ext_dep_lib.lint",
    size = "small",
    srcs = [":python_app_with_ext_dep_lib"],
    tags = ["lint"],
)

ruff_test(
    name = "python_app_with_ext_dep.lint",
    size = "small",
    srcs = [":python_app_with_ext_dep"],
    tags = ["lint"],
)

image_publish(
    name = "publish_image",
    app_prefix = "app",
    artifact_id = "python-app-with-ext-dep",
    base = "@gcr_io_distroless_python3",
    binary_target = ":python_app_with_ext_dep",
    entrypoint = ["/app/python_app_with_ext_dep"],
    strip_prefix = "modules/python_app_with_ext_dep",
)
