load("@rules_go//go:def.bzl", "go_library", "go_test")
load("//tools/publish/lang:generic_publish_defs.bzl", "library_archive_publish")

package(default_visibility = ["//visibility:public"])

library_archive_publish(
    name = "publish",
    artifact_id = "go-lib",
    library_target = ":go_lib",
)

go_library(
    name = "go_lib",
    srcs = glob(["src/**/*.go"]),
    deps = [],
)

go_test(
    name = "go_lib_test",
    size = "small",
    srcs = glob(["tests/**/*.go"]),
    embed = [":go_lib"],  # Use embed for internal tests (same package)
    deps = [
        "@com_github_stretchr_testify//assert",
    ],
)
