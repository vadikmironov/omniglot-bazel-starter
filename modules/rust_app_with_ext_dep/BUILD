load("@rules_rust//rust:defs.bzl", "rust_binary")
load("//tools/lint:linters.bzl", "clippy_test")
load("//tools/publish/lang:generic_publish_defs.bzl", "binary_bundle_publish")
load("//tools/publish/lang:image_publish_defs.bzl", "image_publish")

package(default_visibility = ["//visibility:public"])

binary_bundle_publish(
    name = "publish",
    artifact_id = "rust-app-with-ext-dep",
    binary_target = ":rust_app_with_ext_dep",
)

rust_binary(
    name = "rust_app_with_ext_dep",
    srcs = ["src/main.rs"],
    deps = [
        "@crates//:august",
        "@crates//:reqwest",
        "@crates//:tokio",
    ],
)

clippy_test(
    name = "rust_app_with_ext_dep.lint",
    size = "small",
    srcs = [":rust_app_with_ext_dep"],
    tags = ["lint"],
)

image_publish(
    name = "publish_image",
    app_prefix = "app",
    artifact_id = "rust-app-with-ext-dep",
    base = "@gcr_io_distroless_cc",
    binary_target = ":rust_app_with_ext_dep",
    entrypoint = ["/app/rust_app_with_ext_dep"],
    strip_prefix = "modules/rust_app_with_ext_dep/rust_app_with_ext_dep_",
)
