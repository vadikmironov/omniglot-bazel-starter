"""Forwards the headers of C and C++ dependencies without their libraries."""

load("@rules_cc//cc/common:cc_common.bzl", "cc_common")
load("@rules_cc//cc/common:cc_info.bzl", "CcInfo")

visibility("private")

def _cc_headers_only_impl(ctx):
    return [CcInfo(
        compilation_context = cc_common.merge_compilation_contexts(
            compilation_contexts = [dep[CcInfo].compilation_context for dep in ctx.attr.deps],
        ),
    )]

cc_headers_only = rule(
    implementation = _cc_headers_only_impl,
    attrs = {
        "deps": attr.label_list(
            providers = [CcInfo],
            doc = "Libraries whose headers, include paths and defines are forwarded.",
        ),
    },
    doc = """\
Provides the compilation context of `deps` and nothing to link.

A cc_library dependency, `implementation_deps` included, also puts the
dependency's archives on every downstream link line, so Bazel builds them.
SDL loads these libraries at runtime by soname and only compiles against
their headers, which is all this forwards.
""",
)
