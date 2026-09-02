# Build file for the official CMake Windows ARM64 release archive.

load("@rules_foreign_cc//toolchains/native_tools:native_tools_toolchain.bzl", "native_tool_toolchain")

package(default_visibility = ["//visibility:public"])

filegroup(
    name = "cmake_bin",
    srcs = ["bin/cmake.exe"],
)

# cmake needs its Modules and Templates alongside the binary, not just the exe.
filegroup(
    name = "cmake_data",
    srcs = glob(
        ["**"],
        exclude = [
            "WORKSPACE",
            "WORKSPACE.bazel",
            "BUILD",
            "BUILD.bazel",
            "**/* *",
        ],
    ),
)

native_tool_toolchain(
    name = "cmake_tool",
    env = {"CMAKE": "$(execpath :cmake_bin)"},
    path = "bin/cmake.exe",
    target = ":cmake_data",
    tools = [":cmake_bin"],
)
