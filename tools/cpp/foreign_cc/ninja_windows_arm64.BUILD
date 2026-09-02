# Build file for the official Ninja Windows ARM64 release archive.

load("@rules_foreign_cc//toolchains/native_tools:native_tools_toolchain.bzl", "native_tool_toolchain")

package(default_visibility = ["//visibility:public"])

filegroup(
    name = "ninja_bin",
    srcs = ["ninja.exe"],
)

native_tool_toolchain(
    name = "ninja_tool",
    env = {"NINJA": "$(execpath :ninja_bin)"},
    path = "$(execpath :ninja_bin)",
    target = ":ninja_bin",
)
