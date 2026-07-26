load("@rules_go//go:def.bzl", "go_binary", "go_library", "go_test")

# =========================================================================
# pb2folded — pprof protobuf -> folded stacks (or a multi-value TSV table)
#
# Replaces felixge/pprofutils, which folded a hardcoded sample index and so
# rendered Go/C++ heap object counts under a "bytes" label.
# =========================================================================

go_library(
    name = "pb2folded_lib",
    srcs = ["main.go"],
    importpath = "omniglot-bazel-starter/tools/profile/pb2folded",
    visibility = ["//visibility:private"],
    deps = ["@com_github_google_pprof//profile"],
)

go_binary(
    name = "pb2folded",
    embed = [":pb2folded_lib"],
    # The runner in //tools/profile, plus its sibling test package.
    visibility = ["//tools/profile:__subpackages__"],
)

go_test(
    name = "pb2folded_test",
    size = "small",
    srcs = ["main_test.go"],
    embed = [":pb2folded_lib"],
)
