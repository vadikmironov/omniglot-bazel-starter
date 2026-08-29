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
    # rules_foreign_cc matches out_static_libs literally, and the name varies on
    # two axes: MSVC produces fmt.lib rather than libfmt.a, and fmt appends
    # FMT_DEBUG_POSTFIX ("d") in Debug builds, which -c dbg selects. The postfix
    # cannot simply be pinned off -- rules_foreign_cc drops any cache entry whose
    # value is empty (_wipe_empty_values), so fmt's own default would win.
    out_static_libs = select({
        ":windows_dbg": ["fmtd.lib"],
        "@platforms//os:windows": ["fmt.lib"],
        ":dbg": ["libfmtd.a"],
        "//conditions:default": ["libfmt.a"],
    }),
)

config_setting(
    name = "dbg",
    values = {"compilation_mode": "dbg"},
)

config_setting(
    name = "windows_dbg",
    constraint_values = ["@platforms//os:windows"],
    values = {"compilation_mode": "dbg"},
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
