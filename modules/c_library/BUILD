load("//tools/lint:linters.bzl", "clang_tidy_test")

# gazelle:publish_ignore

load("@rules_cc//cc:defs.bzl", "cc_library")

package(default_visibility = ["//visibility:public"])

cc_library(
    name = "c_library",
    srcs = glob(["src/**/*.c"]),
    hdrs = glob(["include/**/*.h"]),
    includes = ["include"],
    deps = [],
)

clang_tidy_test(
    name = "c_library.lint",
    size = "small",
    srcs = [":c_library"],
    tags = ["lint"],
)
