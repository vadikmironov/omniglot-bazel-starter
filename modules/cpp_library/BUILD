load("@rules_cc//cc:defs.bzl", "cc_library", "cc_test")
load("//tools/lint:linters.bzl", "clang_tidy_test")
load("//tools/publish/lang:generic_publish_defs.bzl", "library_archive_publish")

package(default_visibility = ["//visibility:public"])

library_archive_publish(
    name = "publish",
    hdrs = glob(["include/**/*.h"]),
    artifact_id = "cpp-library",
    library_target = ":cpp_library",
)

cc_library(
    name = "cpp_library",
    srcs = glob(["src/**/*.cpp"]),
    hdrs = glob(["include/**/*.h"]),
    includes = ["include"],
    deps = [],
)

cc_test(
    name = "cpp_library_test",
    size = "small",
    srcs = glob(["tests/**/*.cpp"]),
    linkstatic = True,
    deps = [
        ":cpp_library",
        "@googletest//:gtest",
        "@googletest//:gtest_main",
    ],
)

clang_tidy_test(
    name = "cpp_library.lint",
    size = "small",
    srcs = [":cpp_library"],
    tags = ["lint"],
)
