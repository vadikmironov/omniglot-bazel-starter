"""Module extension that discovers the host Python interpreter for the local
(non-hermetic) Python toolchain, mirroring the auto-discovery of the host C++
toolchains (//tools/cpp/toolchains:host_cc_discovery.bzl).

Instead of pinning a specific interpreter path, the extension probes PATH for
the newest python3.X binary (falling back to plain python3) and wires it through
rules_python's local_runtime_repo / local_runtime_toolchains_repo:
  https://rules-python.readthedocs.io/en/latest/toolchains.html#local-toolchain

Select with --config=python_host (see .bazelrc). The generated repos are
fetched lazily, so machines without a host Python are unaffected until the
config is actually used. Refresh after an interpreter upgrade with
`bazel fetch --configure --force`.
"""

load(
    "@rules_python//python/local_toolchains:repos.bzl",
    "local_runtime_repo",
    "local_runtime_toolchains_repo",
)

def _host_python_discovery_impl(module_ctx):
    # Newest minor first; anything below 3.9 is EOL and not worth probing.
    # Bare names are resolved via which() by local_runtime_repo itself, but we
    # probe here too so a versioned binary (python3.14) wins over plain python3,
    # which distros often point at an older minor.
    interpreter = "python3"
    for minor in range(20, 8, -1):
        candidate = "python3.%d" % minor
        if module_ctx.which(candidate) != None:
            interpreter = candidate
            break

    local_runtime_repo(
        name = "host_python_repo",
        interpreter_path = interpreter,
        on_failure = "fail",
    )
    local_runtime_toolchains_repo(
        name = "host_python_toolchain",
        runtimes = ["host_python_repo"],
    )

    # Machine-local discovery: keep the result out of MODULE.bazel.lock.
    return module_ctx.extension_metadata(reproducible = True)

host_python_discovery = module_extension(
    implementation = _host_python_discovery_impl,
    doc = "Discovers the newest host python3.X on PATH and wires it as a local toolchain.",
)
