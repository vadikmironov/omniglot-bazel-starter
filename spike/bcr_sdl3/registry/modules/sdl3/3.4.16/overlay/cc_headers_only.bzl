"""Forwards the headers of C and C++ dependencies without their libraries."""

load("@rules_cc//cc/common:cc_common.bzl", "cc_common")
load("@rules_cc//cc/common:cc_info.bzl", "CcInfo")

visibility("private")

def _cc_headers_only_impl(ctx):
    merged = cc_common.merge_compilation_contexts(
        compilation_contexts = [dep[CcInfo].compilation_context for dep in ctx.attr.deps],
    )
    return [
        # The headers themselves, so building this target generates them.
        DefaultInfo(files = merged.headers),
        CcInfo(compilation_context = cc_common.create_compilation_context(
            framework_includes = merged.framework_includes,
            headers = merged.headers,
            includes = merged.includes,
            quote_includes = merged.quote_includes,
            system_includes = merged.system_includes,
        )),
    ]

cc_headers_only = rule(
    implementation = _cc_headers_only_impl,
    attrs = {
        "deps": attr.label_list(
            providers = [CcInfo],
            doc = "Libraries whose headers and include paths are forwarded.",
        ),
    },
    doc = """\
Provides the headers and include paths of `deps` and nothing to link.

A cc_library dependency, `implementation_deps` included, also puts the
dependency's archives on every downstream link line, so Bazel builds them.
SDL loads these libraries at runtime by soname and only compiles against
their headers, which is all this forwards.

The defines of `deps` are dropped. They belong to those libraries' own builds
(libX11 exports its `XCMSDIR` and `XLOCALELIBDIR` paths, for one), and a
dependency that starts exporting a `HAVE_*` name would silently change which
features SDL compiles. Include paths are kept, as `-isystem` entries searched
after the headers of the target being built.
""",
)
