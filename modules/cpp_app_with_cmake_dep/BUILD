# gazelle:publish_ignore

load("@rules_cc//cc:defs.bzl", "cc_binary")
load("@rules_foreign_cc//foreign_cc:defs.bzl", "cmake")
load("//tools/lint:linters.bzl", "clang_tidy_test")

package(default_visibility = ["//visibility:public"])

# Build fmt from its own CMakeLists.txt. The cmake() rule runs cmake (and ninja)
# in a sandbox using the rules_foreign_cc toolchains, then exposes the result
# (libfmt.a plus its headers) as a CcInfo provider — so downstream cc rules
# depend on it exactly like a native cc_library.
cmake(
    name = "fmt",
    cache_entries = {
        # fmt builds its test/doc targets when it is the top-level CMake
        # project; we only need the library.
        "FMT_TEST": "OFF",
        "FMT_DOC": "OFF",
    },
    lib_source = "@fmt_src//:all_srcs",
    # Below block is not strictly required and is only added to demonstrate a
    # linkage for CMake project with multiple targets . Unfortunately, this
    # forces special branch for Windows to avoid producing ar archives with
    # lib extension on Linux/MacOS.
    out_static_libs = select({
        "@platforms//os:windows": [
            "fmt.lib",
            "fmt-c.lib",
        ],
        "//conditions:default": [
            "libfmt.a",
            "libfmt-c.a",
        ],
    }),
)

cc_binary(
    name = "cpp_app_with_cmake_dep",
    srcs = ["src/main.cpp"],
    deps = [":fmt"],
)

clang_tidy_test(
    name = "cpp_app_with_cmake_dep.lint",
    size = "small",
    srcs = [":cpp_app_with_cmake_dep"],
    tags = ["lint"],
)
