load("@rules_go//go:def.bzl", "go_binary")
load("//tools/publish/lang:generic_publish_defs.bzl", "binary_bundle_publish")
load("//tools/publish/lang:image_publish_defs.bzl", "image_publish")

package(default_visibility = ["//visibility:public"])

binary_bundle_publish(
    name = "publish",
    artifact_id = "go-app",
    binary_target = ":go_app",
)

go_binary(
    name = "go_app",
    srcs = ["src/main.go"],
    deps = ["//modules/go_lib"],
)

image_publish(
    name = "publish_image",
    app_prefix = "app",
    artifact_id = "go-app",
    base = "@gcr_io_distroless_static",
    binary_target = ":go_app",
    entrypoint = ["/app/go_app"],
    strip_prefix = "modules/go_app/go_app_",
)
