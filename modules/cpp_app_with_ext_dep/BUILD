load("@rules_cc//cc:defs.bzl", "cc_binary")
load("//tools/lint:linters.bzl", "clang_tidy_test")
load("//tools/publish/lang:generic_publish_defs.bzl", "binary_bundle_publish")
load("//tools/publish/lang:image_publish_defs.bzl", "image_publish")

package(default_visibility = ["//visibility:public"])

binary_bundle_publish(
    name = "publish",
    artifact_id = "cpp-app-with-ext-dep",
    binary_target = ":cpp_app_with_ext_dep",
)

cc_binary(
    name = "cpp_app_with_ext_dep",
    srcs = ["src/main.cpp"],
    deps = [
        "@curl",
        "@libxml2",
    ],
)

clang_tidy_test(
    name = "cpp_app_with_ext_dep.lint",
    size = "small",
    srcs = [":cpp_app_with_ext_dep"],
    tags = ["lint"],
)

image_publish(
    name = "publish_image",
    app_prefix = "app",
    artifact_id = "cpp-app-with-ext-dep",
    base = "@gcr_io_distroless_cc",
    binary_target = ":cpp_app_with_ext_dep",
    entrypoint = ["/app/cpp_app_with_ext_dep"],
    strip_prefix = "modules/cpp_app_with_ext_dep",
)
