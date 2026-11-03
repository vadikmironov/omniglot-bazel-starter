load("@rules_cc//cc:defs.bzl", "cc_binary")
load("//tools/lint:linters.bzl", "clang_tidy_test")

# Linted by CI's C++ linter check under hermetic GCC; see the source.
# <immintrin.h> is x86 only.
cc_binary(
    name = "gcc_builtin_headers",
    testonly = True,
    srcs = ["gcc_builtin_headers.cpp"],
    target_compatible_with = ["@platforms//cpu:x86_64"],
)

clang_tidy_test(
    name = "gcc_builtin_headers.lint",
    size = "small",
    srcs = [":gcc_builtin_headers"],
    tags = ["lint"],
)
