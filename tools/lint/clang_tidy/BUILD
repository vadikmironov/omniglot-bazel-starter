load("@rules_cc//cc:defs.bzl", "cc_binary", "cc_library", "cc_test")
load("//tools/lint:linters.bzl", "clang_tidy_test")

# The aspect builds clang_tidy for the exec platform, where --cxxopt doesn't
# apply, so the targets it builds name the repo's C++ standard themselves.
_EXEC_COPTS = ["-std=c++23"]

# clang-tidy from the LLVM toolchain, for the aspect in //tools/lint:linters.bzl.
# Under --config=gcc_hermetic, it gets clang's built-in headers in place of
# GCC's (see main.cpp). toolchains_llvm has no Windows support
# (bazel-contrib/toolchains_llvm#4), so clang-tidy doesn't run there.
cc_binary(
    name = "clang_tidy",
    srcs = ["main.cpp"],
    copts = _EXEC_COPTS,
    data = [
        "@llvm_toolchain_llvm//:bin/clang-tidy",
        # clang's built-in headers (and libc++'s) as two directories, where
        # :include would bring some 9,000 LLVM headers as well.
        "@llvm_toolchain_llvm//:cxx_builtin_include",
    ],
    visibility = ["//tools/lint:__pkg__"],
    deps = [
        ":args",
        "@rules_cc//cc/runfiles",
    ],
)

cc_library(
    name = "args",
    srcs = ["args.cpp"],
    hdrs = ["args.h"],
    copts = _EXEC_COPTS,
)

cc_test(
    name = "args_test",
    size = "small",
    srcs = ["args_test.cpp"],
    deps = [
        ":args",
        "@googletest//:gtest",
        "@googletest//:gtest_main",
    ],
)

# Linted under --config=gcc_hermetic by CI, to catch the wrapper regressing
# (see the source). <immintrin.h> is x86 only.
cc_binary(
    name = "intrinsics_fixture",
    testonly = True,
    srcs = ["intrinsics_fixture.cpp"],
    target_compatible_with = ["@platforms//cpu:x86_64"],
)

clang_tidy_test(
    name = "clang_tidy.lint",
    size = "small",
    srcs = [":clang_tidy"],
    tags = ["lint"],
)

clang_tidy_test(
    name = "args.lint",
    size = "small",
    srcs = [":args"],
    tags = ["lint"],
)

clang_tidy_test(
    name = "intrinsics_fixture.lint",
    size = "small",
    srcs = [":intrinsics_fixture"],
    tags = ["lint"],
)
