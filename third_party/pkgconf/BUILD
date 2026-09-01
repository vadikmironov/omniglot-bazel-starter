# pkg-config toolchain backed by pkgconf, built from source in @pkgconf_src.
#
# Registered from the root module, which outranks the toolchain rules_foreign_cc
# registers for itself, so cmake()/make()/meson() targets resolve to this one.

load("@rules_foreign_cc//toolchains/native_tools:native_tools_toolchain.bzl", "native_tool_toolchain")

package(default_visibility = ["//visibility:public"])

native_tool_toolchain(
    name = "pkgconf",
    env = {"PKG_CONFIG": "$(execpath @pkgconf_src//:pkgconf)"},
    path = "$(execpath @pkgconf_src//:pkgconf)",
    target = "@pkgconf_src//:pkgconf",
)

toolchain(
    name = "pkgconf_toolchain",
    toolchain = ":pkgconf",
    toolchain_type = "@rules_foreign_cc//toolchains:pkgconfig_toolchain",
)
