"""Development virtual environment from uv.lock.

`bazel run` of a `create_venv` target runs `uv sync` with the uv binary from
rules_python's uv toolchain and the interpreter from the resolved Python
toolchain, so the venv matches the hermetic build. Bash hosts only.
"""

_UV_TOOLCHAIN = "@rules_python//python/uv:uv_toolchain_type"
_PY_TOOLCHAIN = "@bazel_tools//tools/python:toolchain_type"

def _interpreter(runtime):
    # Hermetic runtimes ship the interpreter as a file; local ones only know its path.
    if runtime.interpreter:
        return runtime.interpreter.short_path
    return runtime.interpreter_path

def _create_venv_impl(ctx):
    uv = ctx.toolchains[_UV_TOOLCHAIN].uv_toolchain_info.uv[DefaultInfo]
    runtime = ctx.toolchains[_PY_TOOLCHAIN].py3_runtime
    script = ctx.actions.declare_file(ctx.label.name + ".sh")
    ctx.actions.expand_template(
        template = ctx.file._template,
        output = script,
        is_executable = True,
        substitutions = {
            "{{destination_folder}}": ctx.attr.destination_folder,
            "{{project_dir}}": ctx.file.pyproject.dirname,
            "{{python}}": _interpreter(runtime),
            "{{uv}}": uv.files_to_run.executable.short_path,
        },
    )
    runfiles = ctx.runfiles(
        files = [uv.files_to_run.executable, ctx.file.pyproject, ctx.file.lock],
        transitive_files = runtime.files,
    ).merge(uv.default_runfiles)
    return [DefaultInfo(executable = script, runfiles = runfiles)]

create_venv = rule(
    implementation = _create_venv_impl,
    doc = "Creates or refreshes a venv from a uv.lock via `uv sync --all-groups --locked`.",
    attrs = {
        "destination_folder": attr.string(
            default = ".venv",
            doc = "Venv path relative to the workspace root.",
        ),
        "lock": attr.label(
            mandatory = True,
            allow_single_file = True,
            doc = "The uv.lock next to `pyproject`.",
        ),
        "pyproject": attr.label(
            mandatory = True,
            allow_single_file = True,
            doc = "The pyproject.toml whose directory is the uv project.",
        ),
        "_template": attr.label(
            default = ":create_venv.sh.tpl",
            allow_single_file = True,
        ),
    },
    executable = True,
    toolchains = [_UV_TOOLCHAIN, _PY_TOOLCHAIN],
)
