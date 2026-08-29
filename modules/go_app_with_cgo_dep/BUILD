# gazelle:publish_ignore

load("@rules_go//go:def.bzl", "go_binary")

package(default_visibility = ["//visibility:public"])

# Not buildable on Windows: cgo parses GCC-style compiler diagnostics, so
# rules_go denylists msvc-cl and clang-cl (_UNSUPPORTED_C_COMPILERS in
# go/private/context.bzl) and silently reports cgo as unavailable. Both sources
# are then dropped by build constraints and the link fails with "not package
# main". Enabling it would mean a MinGW toolchain alongside the MSVC one.
go_binary(
    name = "go_app_with_cgo_dep",
    srcs = [
        "src/cfuncs.go",
        "src/main.go",
    ],
    cdeps = ["//modules/c_library"],
    cgo = True,
    target_compatible_with = select({
        "@platforms//os:windows": ["@platforms//:incompatible"],
        "//conditions:default": [],
    }),
)
