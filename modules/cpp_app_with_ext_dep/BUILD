# gazelle:publish_ignore

load("@rules_cc//cc:defs.bzl", "cc_binary")
load("//tools/lint:linters.bzl", "clang_tidy_test")

package(default_visibility = ["//visibility:public"])

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
