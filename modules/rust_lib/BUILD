load("@rules_rust//rust:defs.bzl", "rust_library", "rust_test")
load("//tools/lint:linters.bzl", "clippy_test")
load("//tools/publish/lang:generic_publish_defs.bzl", "library_archive_publish")

package(default_visibility = ["//visibility:public"])

library_archive_publish(
    name = "publish",
    artifact_id = "rust-lib",
    library_target = ":rust_lib",
)

rust_library(
    name = "rust_lib",
    srcs = glob(["src/**/*.rs"]),
    crate_features = ["default"],
    crate_root = "src/hello_world_lib.rs",
)

rust_test(
    name = "rust_lib_test",
    timeout = "short",
    srcs = glob(["tests/**/*.rs"]),
    deps = [":rust_lib"],
)

clippy_test(
    name = "rust_lib.lint",
    size = "small",
    srcs = [":rust_lib"],
    tags = ["lint"],
)

clippy_test(
    name = "rust_lib_test.lint",
    size = "small",
    srcs = [":rust_lib_test"],
    tags = ["lint"],
)
