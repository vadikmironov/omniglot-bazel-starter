load("@rules_go//go:def.bzl", "go_binary")
load("//tools/publish/lang:generic_publish_defs.bzl", "binary_bundle_publish")
load("//tools/publish/lang:image_publish_defs.bzl", "image_publish")

package(default_visibility = ["//visibility:public"])

binary_bundle_publish(
    name = "publish",
    artifact_id = "go-app-with-ext-dep",
    binary_target = ":go_app_with_ext_dep",
)

go_binary(
    name = "go_app_with_ext_dep",
    srcs = ["src/main.go"],
    deps = [
        "@org_golang_x_net//html",
    ],
)

image_publish(
    name = "publish_image",
    app_prefix = "app",
    artifact_id = "go-app-with-ext-dep",
    base = "@gcr_io_distroless_static",
    binary_target = ":go_app_with_ext_dep",
    entrypoint = ["/app/go_app_with_ext_dep"],
    strip_prefix = "modules/go_app_with_ext_dep/go_app_with_ext_dep_",
)
