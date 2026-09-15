"""Forwards the headers of C and C++ dependencies without their libraries."""

load("@rules_cc//cc/common:cc_common.bzl", "cc_common")
load("@rules_cc//cc/common:cc_info.bzl", "CcInfo")

visibility("private")

def _cc_headers_only_impl(ctx):
    merged = cc_common.merge_compilation_contexts(
        compilation_contexts = [dep[CcInfo].compilation_context for dep in ctx.attr.deps],
    )
    excluded = {dep.label.repo_name: True for dep in ctx.attr.exclude_headers_from}
    headers = [h for h in merged.headers.to_list() if h.owner.repo_name not in excluded]
    return [CcInfo(
        compilation_context = cc_common.create_compilation_context(
            defines = merged.defines,
            framework_includes = merged.framework_includes,
            headers = depset(headers),
            includes = merged.includes,
            quote_includes = merged.quote_includes,
            system_includes = merged.system_includes,
        ),
    )]

cc_headers_only = rule(
    implementation = _cc_headers_only_impl,
    attrs = {
        "deps": attr.label_list(
            providers = [CcInfo],
            doc = "Libraries whose headers, include paths and defines are forwarded.",
        ),
        "exclude_headers_from": attr.label_list(
            doc = "Targets whose repositories' headers are left out: headers the " +
                  "consumer never includes, whose generation would otherwise run.",
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
