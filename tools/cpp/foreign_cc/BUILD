# Windows ARM64 only: rules_foreign_cc has no prebuilt cmake or ninja for that
# platform, and its system fallback would take whatever is on the host PATH.
# Registered from the root module and constrained to ARM64, so the upstream
# prebuilts keep winning everywhere else.

package(default_visibility = ["//visibility:public"])

toolchain(
    name = "cmake_windows_arm64_toolchain",
    exec_compatible_with = [
        "@platforms//cpu:arm64",
        "@platforms//os:windows",
    ],
    toolchain = "@cmake_windows_arm64//:cmake_tool",
    toolchain_type = "@rules_foreign_cc//toolchains:cmake_toolchain",
)

toolchain(
    name = "ninja_windows_arm64_toolchain",
    exec_compatible_with = [
        "@platforms//cpu:arm64",
        "@platforms//os:windows",
    ],
    toolchain = "@ninja_windows_arm64//:ninja_tool",
    toolchain_type = "@rules_foreign_cc//toolchains:ninja_toolchain",
)
