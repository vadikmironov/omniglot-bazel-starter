load("@rules_rust//rust:defs.bzl", "rust_binary")
load("//tools/lint:linters.bzl", "clippy_test")
load("//tools/publish/lang:generic_publish_defs.bzl", "binary_bundle_publish")
load("//tools/publish/lang:image_publish_defs.bzl", "image_publish")

package(default_visibility = ["//visibility:public"])

binary_bundle_publish(
    name = "publish",
    artifact_id = "rust-app",
    binary_target = ":rust_app",
)

rust_binary(
    name = "rust_app",
    srcs = ["src/main.rs"],
    deps = ["//modules/rust_lib"],
)

clippy_test(
    name = "rust_app.lint",
    size = "small",
    srcs = [":rust_app"],
    tags = ["lint"],
)

image_publish(
    name = "publish_image",
    app_prefix = "app",
    artifact_id = "rust-app",
    base = "@gcr_io_distroless_cc",
    binary_target = ":rust_app",
    entrypoint = ["/app/rust_app"],
    strip_prefix = "modules/rust_app/rust_app_",
)
