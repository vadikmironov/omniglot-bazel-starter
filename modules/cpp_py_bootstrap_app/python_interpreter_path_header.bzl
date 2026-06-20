"""Rule to generate a C++ header with the Python interpreter's runfiles path.

Handles both hermetic and local (platform) Python toolchains:
- Hermetic: emits the interpreter's runfiles-relative short_path
- Local/platform: emits an empty string (runtime falls back to env-based resolution)
"""

def _python_interpreter_path_header_impl(ctx):
    toolchain = ctx.toolchains["@rules_python//python:toolchain_type"]

    path = ""
    if toolchain.py3_runtime and toolchain.py3_runtime.interpreter:
        path = toolchain.py3_runtime.interpreter.short_path

    header = ctx.actions.declare_file(ctx.attr.header_name)
    ctx.actions.write(header, '#define RULES_PYTHON_RUNFILES_PATH "{}"\n'.format(path))
    return [DefaultInfo(files = depset([header]))]

python_interpreter_path_header = rule(
    implementation = _python_interpreter_path_header_impl,
    attrs = {
        "header_name": attr.string(
            default = "rules_python_current_interpreter_path_header.h",
            doc = "Output header filename (must match the #include in C++ sources)",
        ),
    },
    toolchains = ["@rules_python//python:toolchain_type"],
)
