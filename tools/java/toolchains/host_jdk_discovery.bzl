"""Module extension that discovers system-installed JDKs for the local host
Java toolchain, mirroring the auto-discovery of the host C++ toolchains
(//tools/cpp/toolchains:host_cc_discovery.bzl) and host Python
(//tools/python/toolchains:host_python_discovery.bzl).

Instead of pinning a java_home path, the extension enumerates JDK
installations (JAVA_HOME plus the conventional distro directories) and wires
the newest one via rules_java's local_java_repository under the stable repo
name local_host_jdk_toolchain, so the .bazelrc java_host config never changes
with the installed JDK. The language level stays whatever the build requests
(--java_language_version, default 17): a newer runtime compiles and runs
older language levels, so the newest JDK always satisfies it.

If no JDK is discovered, the repo falls back to Debian's default-java
symlink; selecting the config then fails with a clear "java_home ... does not
exist" message, while unselected builds are unaffected (repos fetch lazily).
Refresh after installing or removing a JDK with `bazel fetch --configure --force`.
"""

load("@rules_java//toolchains:local_java_repository.bzl", "local_java_repository")

# Conventional distro install directories to enumerate (JAVA_HOME is probed too).
_SEARCH_DIRS = [
    "/usr/lib/jvm",  # Debian/Ubuntu/Fedora
    "/usr/java",  # Oracle/Corretto RPM layout
]

# Fallback when discovery finds nothing: Debian's default-java symlink, so the
# failure message names a conventional location (and may even resolve).
_FALLBACK_JAVA_HOME = "/usr/lib/jvm/default-java"

def _jdk_major_version(module_ctx, java_home):
    """Parses the JDK's `release` file for its major version, or None."""
    release = java_home + "/release"
    if not module_ctx.path(release).exists:
        return None
    for line in module_ctx.read(release).splitlines():
        if line.startswith("JAVA_VERSION="):
            version = line[len("JAVA_VERSION="):].strip().strip('"')
            parts = version.split(".")

            # Pre-9 scheme: "1.8.0_452" -> 8
            if parts[0] == "1" and len(parts) > 1:
                return int(parts[1].split("_")[0])
            elif parts[0].isdigit():
                return int(parts[0])
            return None
    return None

def _discover_jdks(module_ctx):
    """Returns {major_version: java_home}, deduplicated via realpath."""
    candidates = []
    java_home_env = module_ctx.os.environ.get("JAVA_HOME")
    if java_home_env:
        candidates.append(java_home_env)
    for directory in _SEARCH_DIRS:
        if not module_ctx.path(directory).exists:
            continue
        result = module_ctx.execute(["ls", "-1", directory])
        if result.return_code != 0:
            continue
        candidates.extend([
            directory + "/" + entry
            for entry in result.stdout.strip().split("\n")
            if entry
        ])

    found = {}
    seen_realpaths = {}
    for candidate in candidates:
        path = module_ctx.path(candidate)

        # A usable JDK has bin/java; skip JRE-only or partial installs.
        if not path.exists or not module_ctx.path(candidate + "/bin/java").exists:
            continue
        realpath = str(path.realpath)
        if realpath in seen_realpaths:  # distros symlink several aliases to one JDK
            continue
        seen_realpaths[realpath] = True
        major = _jdk_major_version(module_ctx, realpath)
        if major != None and major not in found:
            found[major] = realpath
    return found

def _host_jdk_discovery_impl(module_ctx):
    found = {} if module_ctx.os.name.startswith("windows") else _discover_jdks(module_ctx)
    newest = max(found.keys()) if found else None
    local_java_repository(
        name = "local_host_jdk_toolchain",
        java_home = found[newest] if newest != None else _FALLBACK_JAVA_HOME,
        version = str(newest) if newest != None else "",
    )

    # Machine-local discovery: keep the result out of MODULE.bazel.lock.
    return module_ctx.extension_metadata(reproducible = True)

host_jdk_discovery = module_extension(
    implementation = _host_jdk_discovery_impl,
    doc = "Discovers system JDKs and wires the newest as the local host Java toolchain.",
)
