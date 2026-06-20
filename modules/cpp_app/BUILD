load("@rules_cc//cc:defs.bzl", "cc_binary")
load("//tools/lint:linters.bzl", "clang_tidy_test")
load("//tools/publish/lang:generic_publish_defs.bzl", "binary_bundle_publish")
load("//tools/publish/lang:image_publish_defs.bzl", "image_publish")

package(default_visibility = ["//visibility:public"])

binary_bundle_publish(
    name = "publish",
    artifact_id = "cpp-app",
    binary_target = ":cpp_app",
)

cc_binary(
    name = "cpp_app",
    srcs = ["src/main.cpp"],
    visibility = ["//visibility:public"],
    deps = ["//modules/cpp_library"],
)

clang_tidy_test(
    name = "cpp_app.lint",
    size = "small",
    srcs = [":cpp_app"],
    tags = ["lint"],
)

image_publish(
    name = "publish_image",
    app_prefix = "app",
    artifact_id = "cpp-app",
    base = "@gcr_io_distroless_cc",
    binary_target = ":cpp_app",
    entrypoint = ["/app/cpp_app"],
    strip_prefix = "modules/cpp_app",
)
