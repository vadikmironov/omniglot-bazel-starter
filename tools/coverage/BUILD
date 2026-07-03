load("@rules_shell//shell:sh_binary.bzl", "sh_binary")

# Referenced as the build_file for the @lcov http_archive (see
# coverage_segment.MODULE.bazel).
exports_files(["lcov.BUILD.bazel"])

# Renders the combined LCOV report to an HTML tree via the hermetic lcov genhtml.
# Prerequisite: bazel coverage --combined_report=lcov //...
sh_binary(
    name = "report",
    srcs = ["report.sh"],
    args = ["$(rlocationpath @lcov//:genhtml)"],
    data = ["@lcov//:genhtml"],
    visibility = ["//visibility:public"],
    deps = ["@rules_shell//shell/runfiles"],
)
