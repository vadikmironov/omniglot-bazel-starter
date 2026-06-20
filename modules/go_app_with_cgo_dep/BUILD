# gazelle:publish_ignore

load("@rules_go//go:def.bzl", "go_binary")

package(default_visibility = ["//visibility:public"])

go_binary(
    name = "go_app_with_cgo_dep",
    srcs = [
        "src/cfuncs.go",
        "src/main.go",
    ],
    cdeps = ["//modules/c_library"],
    cgo = True,
)
