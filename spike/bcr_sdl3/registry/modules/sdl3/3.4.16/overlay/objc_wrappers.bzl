"""Writes one C file per Objective-C source, each including it."""

visibility("private")

def _src_path(src):
    """The source's path from the repository root, as its label spells it."""
    label = src.owner
    return label.package + "/" + label.name if label.package else label.name

def _objc_wrappers_impl(ctx):
    outputs = []
    for src in ctx.files.srcs:
        path = _src_path(src)
        wrapper = ctx.actions.declare_file(ctx.attr.prefix + "/" + path + ".c")
        ctx.actions.write(wrapper, "#include \"%s\"\n" % path)
        outputs.append(wrapper)
    return [DefaultInfo(files = depset(outputs))]

objc_wrappers = rule(
    implementation = _objc_wrappers_impl,
    attrs = {
        "prefix": attr.string(
            default = "objc",
            doc = "Directory the generated files go in.",
        ),
        "srcs": attr.label_list(
            allow_files = [".m"],
            doc = "Objective-C sources to wrap.",
        ),
    },
    doc = """\
For each source, a C file that includes it by its path from the repository
root. A cc_library compiles those with `-x objective-c`, which lets any C
toolchain that targets macOS build them; objc_library would accept the `.m`
files directly but only with apple_support's toolchain. Each wrapper is its own
translation unit, and `__FILE__` and the debug line table still name the `.m`.
""",
)
