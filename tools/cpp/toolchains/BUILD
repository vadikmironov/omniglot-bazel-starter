load("@host_cc_discovery//:defs.bzl", "CLANG_BUILTIN_INCLUDE_DIRECTORIES", "CLANG_TOOL_BIN", "GCC_BUILTIN_INCLUDE_DIRECTORIES", "GCC_TOOL_BIN")
load("@rules_cc//cc:defs.bzl", "cc_toolchain")
load(":toolchain_config.bzl", "cc_toolchain_config")

filegroup(name = "empty")

#
# Host gcc toolchain for linux_x86_64
#
cc_toolchain_config(
    name = "host_gcc_linux_x86_64_toolchain_config",
    builtin_include_directories = GCC_BUILTIN_INCLUDE_DIRECTORIES,
    compiler_flavour_name = "gcc_host_local",
    tool_bin_dir = GCC_TOOL_BIN,
)

cc_toolchain(
    name = "host_gcc_linux_x86_64_toolchain",
    all_files = ":empty",
    compiler_files = ":empty",
    dwp_files = ":empty",
    linker_files = ":empty",
    objcopy_files = ":empty",
    strip_files = ":empty",
    supports_param_files = 0,
    toolchain_config = ":host_gcc_linux_x86_64_toolchain_config",
    toolchain_identifier = "host_gcc_linux_x86_64_toolchain",
)

toolchain(
    name = "host_gcc_cc_toolchain_for_linux_x86_64",
    exec_compatible_with = [
        "@platforms//cpu:x86_64",
        "@platforms//os:linux",
    ],
    target_compatible_with = [
        "@platforms//cpu:x86_64",
        "@platforms//os:linux",
    ],
    toolchain = ":host_gcc_linux_x86_64_toolchain",
    toolchain_type = "@bazel_tools//tools/cpp:toolchain_type",
)

#
# Host clang toolchain for linux_x86_64
#
cc_toolchain_config(
    name = "host_clang_linux_x86_64_toolchain_config",
    builtin_include_directories = CLANG_BUILTIN_INCLUDE_DIRECTORIES,
    compiler_flavour_name = "clang_host_local",
    tool_bin_dir = CLANG_TOOL_BIN,
)

cc_toolchain(
    name = "host_clang_linux_x86_64_toolchain",
    all_files = ":empty",
    compiler_files = ":empty",
    dwp_files = ":empty",
    linker_files = ":empty",
    objcopy_files = ":empty",
    strip_files = ":empty",
    supports_param_files = 0,
    toolchain_config = ":host_clang_linux_x86_64_toolchain_config",
    toolchain_identifier = "host_clang_linux_x86_64_toolchain",
)

toolchain(
    name = "host_clang_cc_toolchain_for_linux_x86_64",
    exec_compatible_with = [
        "@platforms//cpu:x86_64",
        "@platforms//os:linux",
    ],
    target_compatible_with = [
        "@platforms//cpu:x86_64",
        "@platforms//os:linux",
    ],
    toolchain = ":host_clang_linux_x86_64_toolchain",
    toolchain_type = "@bazel_tools//tools/cpp:toolchain_type",
)

platform(
    name = "x86_64_linux_platform",
    constraint_values = [
        "@platforms//cpu:x86_64",
        "@platforms//os:linux",
    ],
    visibility = ["//visibility:public"],
)
