"""
Helper module extension to configure all locally installed Amazon Corretto JDKs at once.

Setup: Run local_corretto_toolchains_setup.sh (Linux/macOS) or
local_corretto_toolchains_setup.ps1 (Windows) with --toolchain_root_path argument
(or -ToolchainRootPath / -r on Windows) to download and install Corretto JDKs.

Default installation paths (~ expands to user's home directory):
  - Linux/macOS: ~/.corretto_jdks
  - Windows: ~/.corretto_jdks

To override the default base paths, use the config tag in MODULE.bazel:
    local_corretto_toolchains = use_extension(
        "//tools/java/toolchains:local_corretto_toolchains.bzl",
        "local_corretto_toolchains",
    )
    local_corretto_toolchains.config(
        unix_base_path = "~/.corretto_jdks",
        windows_base_path = "~/.corretto_jdks",
    )

Note: Paths starting with ~ are expanded to the user's home directory
($HOME on Unix, %USERPROFILE% on Windows).

Usage: Set --java_runtime_version flag to the repository name (e.g., local_corretto_jdk17)
or use a .bazelrc config like:
    build:java_17_local --java_runtime_version=local_corretto_jdk17
    build:java_17_local --tool_java_runtime_version=local_corretto_jdk17

Note: If the JDK path doesn't exist or is invalid, a placeholder repository is created
that won't match during toolchain resolution. This allows the build to proceed when
using remote toolchains or other JDK configurations.
"""

load("@bazel_tools//tools/build_defs/repo:utils.bzl", "maybe")
load("@rules_java//toolchains:jdk_build_file.bzl", "JDK_BUILD_TEMPLATE")

# Default base path for local Corretto JDKs (~ expands to home directory)
_DEFAULT_CORRETTO_BASE_PATH = "~/.corretto_jdks"

def _get_home_directory(environ, os_name):
    """Returns the user's home directory from environment variables."""
    if os_name.startswith("windows"):
        # Windows uses USERPROFILE, fallback to HOMEDRIVE+HOMEPATH
        home = environ.get("USERPROFILE")
        if not home:
            drive = environ.get("HOMEDRIVE", "C:")
            path = environ.get("HOMEPATH", "\\Users\\Default")
            home = drive + path
        return home
    else:
        # Unix uses HOME
        return environ.get("HOME", "/tmp")

def _expand_home_path(path, environ, os_name):
    """Expands ~ at the start of a path to the user's home directory."""
    if path.startswith("~/") or path == "~":
        home = _get_home_directory(environ, os_name)
        if path == "~":
            return home
        else:
            return home + path[1:]  # Replace ~ with home, keep the rest
    return path

# JDK directory names (relative to base path)
_LOCAL_CORRETTO_JDK_CONFIGS = [
    struct(
        prefix = "local_corretto_jdk",
        dir_name = "amazon_corretto_jdk_8_latest",
        version = "8",
    ),
    struct(
        prefix = "local_corretto_jdk",
        dir_name = "amazon_corretto_jdk_11_latest",
        version = "11",
    ),
    struct(
        prefix = "local_corretto_jdk",
        dir_name = "amazon_corretto_jdk_17_latest",
        version = "17",
    ),
    struct(
        prefix = "local_corretto_jdk",
        dir_name = "amazon_corretto_jdk_21_latest",
        version = "21",
    ),
    struct(
        prefix = "local_corretto_jdk",
        dir_name = "amazon_corretto_jdk_25_latest",
        version = "25",
    ),
]

# Placeholder BUILD file for missing JDK - creates targets that exist but won't match
_INVALID_JDK_PLACEHOLDER_BUILD_TEMPLATE = """
# Placeholder for missing or invalid local JDK installation at: {java_home}
# Run local_corretto_toolchains_setup.sh to install the JDK.

package(default_visibility = ["//visibility:public"])

filegroup(
    name = "jdk",
    srcs = [],
)
"""

# Placeholder toolchain config BUILD file (for missing JDKs)
# Creates toolchains that never match due to impossible constraint
_INVALID_JDK_TOOLCHAIN_PLACEHOLDER_BUILD_TEMPLATE = """
# Placeholder for missing or invalid local JDK installation: {name}
# Run local_corretto_toolchains_setup.sh to install the JDK.
#
# This placeholder allows the build to proceed when this toolchain is not selected.
# If you explicitly select this toolchain and the JDK is not installed, you will
# get a clear error message.

package(default_visibility = ["//visibility:public"])

filegroup(
    name = "empty",
    srcs = [],
)

# Toolchain that never matches due to impossible constraint
toolchain(
    name = "runtime_toolchain_definition",
    exec_compatible_with = ["@platforms//:incompatible"],
    target_compatible_with = ["@platforms//:incompatible"],
    toolchain = ":empty",
    toolchain_type = "@bazel_tools//tools/jdk:runtime_toolchain_type",
)

toolchain(
    name = "bootstrap_runtime_toolchain_definition",
    exec_compatible_with = ["@platforms//:incompatible"],
    target_compatible_with = ["@platforms//:incompatible"],
    toolchain = ":empty",
    toolchain_type = "@bazel_tools//tools/jdk:bootstrap_runtime_toolchain_type",
)
"""

# Toolchain config BUILD file template (for valid JDKs)
# This is used in a separate *_toolchain_config_repo repository
_TOOLCHAIN_CONFIG_BUILD_TEMPLATE = """
package(default_visibility = ["//visibility:public"])

load("@platforms//host:constraints.bzl", "HOST_CONSTRAINTS")

# Config settings for toolchain resolution via --java_runtime_version flag
config_setting(
    name = "prefix_version_setting",
    values = {{"java_runtime_version": "{prefix}_{version}"}},
    visibility = ["//visibility:private"],
)
config_setting(
    name = "version_setting",
    values = {{"java_runtime_version": "{version}"}},
    visibility = ["//visibility:private"],
)
alias(
    name = "version_or_prefix_version_setting",
    actual = select({{
        ":version_setting": ":version_setting",
        "//conditions:default": ":prefix_version_setting",
    }}),
    visibility = ["//visibility:private"],
)

toolchain(
    name = "toolchain",
    target_compatible_with = HOST_CONSTRAINTS,
    target_settings = [":version_or_prefix_version_setting"],
    toolchain_type = "@bazel_tools//tools/jdk:runtime_toolchain_type",
    toolchain = "{toolchain}",
)

toolchain(
    name = "bootstrap_runtime_toolchain",
    exec_compatible_with = HOST_CONSTRAINTS,
    target_settings = [":version_or_prefix_version_setting"],
    toolchain_type = "@bazel_tools//tools/jdk:bootstrap_runtime_toolchain_type",
    toolchain = "{toolchain}",
)
"""

def _is_valid_jdk(ctx, java_home):
    """Check if the path is a valid JDK installation with required directories.

    Works with both repository_ctx and module_ctx since both have .path() method.

    Args:
        ctx: Either repository_ctx or module_ctx
        java_home: String path to the JDK installation
    """
    java_home_path = ctx.path(java_home)
    if not java_home_path.exists:
        return False

    # Check for essential JDK directories that JDK_BUILD_TEMPLATE expects
    # The template globs for bin/**, lib/**, etc.
    bin_path = ctx.path(java_home + "/bin")
    lib_path = ctx.path(java_home + "/lib")

    return bin_path.exists and lib_path.exists

def _list_directory(repository_ctx, path):
    """List directory contents in a cross-platform way."""
    if repository_ctx.os.name.startswith("windows"):
        # On Windows, use cmd /c dir /b
        result = repository_ctx.execute(["cmd", "/c", "dir", "/b", path])
    else:
        # On Unix-like systems, use ls -1
        result = repository_ctx.execute(["ls", "-1", path])

    if result.return_code == 0:
        return [e for e in result.stdout.strip().split("\n") if e]
    return []

def _optional_local_java_repository_impl(repository_ctx):
    """Repository rule that handles missing JDK paths gracefully."""
    java_home = repository_ctx.attr.java_home
    version = repository_ctx.attr.version

    if _is_valid_jdk(repository_ctx, java_home):
        # JDK exists and is valid - symlink contents to repo root
        # JDK_BUILD_TEMPLATE expects files at the root level (bin/, lib/, etc.)
        entries = _list_directory(repository_ctx, java_home)
        for entry in entries:
            repository_ctx.symlink(java_home + "/" + entry, entry)

        # Create BUILD.bazel with the JDK_BUILD_TEMPLATE from rules_java
        # The template has one placeholder: {RUNTIME_VERSION}
        # NOTE: JDK_BUILD_TEMPLATE does NOT define a runtime toolchain.
        # We must add one explicitly or java_runtime_version will not work.
        build_content = JDK_BUILD_TEMPLATE.format(RUNTIME_VERSION = version)
        repository_ctx.file("BUILD.bazel", build_content)
    else:
        # JDK doesn't exist or is invalid - create placeholder
        # buildifier: disable=print
        print("WARNING: Local JDK not found or invalid at '{}'. ".format(java_home) +
              "Toolchain '{}' will be unavailable. ".format(repository_ctx.attr.name) +
              "Run local_corretto_toolchains_setup.sh to install.")

        build_content = _INVALID_JDK_PLACEHOLDER_BUILD_TEMPLATE.format(java_home = java_home)
        repository_ctx.file("BUILD.bazel", build_content)

_optional_local_java_repository = repository_rule(
    implementation = _optional_local_java_repository_impl,
    attrs = {
        "java_home": attr.string(mandatory = True, doc = "Path to the local JDK installation"),
        "version": attr.string(mandatory = True, doc = "Java version (e.g., '17')"),
    },
    local = True,  # Re-evaluate when local files change
    doc = "Creates a Java runtime repository from a local JDK, with graceful fallback if missing.",
)

# Toolchain config repository rule - creates a separate repository containing only
# the toolchain definitions. This pattern comes from rules_java's remote_java_repository.bzl
# which creates a *_toolchain_config_repo for each JDK. The separation allows:
# 1. The JDK repository to contain only the JDK files (using JDK_BUILD_TEMPLATE)
# 2. The toolchain config repo to contain config_settings and toolchain definitions
# See: https://github.com/bazelbuild/rules_java/blob/master/toolchains/remote_java_repository.bzl
def _local_toolchain_config_impl(repository_ctx):
    """Repository rule that creates toolchain config for a local JDK."""
    repository_ctx.file(
        "WORKSPACE",
        "workspace(name = \"{name}\")\n".format(name = repository_ctx.name),
    )
    repository_ctx.file("BUILD.bazel", repository_ctx.attr.build_file)

_local_toolchain_config = repository_rule(
    implementation = _local_toolchain_config_impl,
    attrs = {
        "build_file": attr.string(mandatory = True, doc = "Content of the BUILD file"),
    },
    local = True,
    doc = "Creates a toolchain config repository for a local JDK.",
)

def _local_corretto_toolchains_impl(module_ctx):
    os_name = module_ctx.os.name
    environ = module_ctx.os.environ

    # Check if user specified custom base paths via tag
    unix_base_path = None
    windows_base_path = None
    for mod in module_ctx.modules:
        for config in mod.tags.config:
            if config.unix_base_path:
                unix_base_path = config.unix_base_path
            if config.windows_base_path:
                windows_base_path = config.windows_base_path
        if unix_base_path and windows_base_path:
            break

    # Select appropriate path based on OS, falling back to default
    if os_name.startswith("windows"):
        base_path = windows_base_path if windows_base_path else _DEFAULT_CORRETTO_BASE_PATH
    else:
        base_path = unix_base_path if unix_base_path else _DEFAULT_CORRETTO_BASE_PATH

    # Expand ~ to home directory
    base_path = _expand_home_path(base_path, environ, os_name)

    for item in _LOCAL_CORRETTO_JDK_CONFIGS:
        repo_name = item.prefix + "_" + item.version
        java_home = base_path + "/" + item.dir_name

        # Create the JDK repository (contains the actual JDK files)
        maybe(
            _optional_local_java_repository,
            name = repo_name,
            java_home = java_home,
            version = item.version,
        )

        # Create the toolchain config repository (contains toolchain definitions)
        # Use different templates based on whether the JDK exists
        if _is_valid_jdk(module_ctx, java_home):
            toolchain_build_file = _TOOLCHAIN_CONFIG_BUILD_TEMPLATE.format(
                prefix = item.prefix,
                version = item.version,
                toolchain = "@{repo}//:jdk".format(repo = repo_name),
            )
        else:
            toolchain_build_file = _INVALID_JDK_TOOLCHAIN_PLACEHOLDER_BUILD_TEMPLATE.format(
                name = repo_name,
            )

        maybe(
            _local_toolchain_config,
            name = repo_name + "_toolchain_config_repo",
            build_file = toolchain_build_file,
        )

    # Machine-local discovery: keep the result out of MODULE.bazel.lock, so a
    # JDK installed after the first build is picked up on re-evaluation instead
    # of being shadowed by a locked placeholder.
    return module_ctx.extension_metadata(reproducible = True)

_config_tag = tag_class(
    attrs = {
        "unix_base_path": attr.string(
            doc = "Base path where Corretto JDKs are installed on Linux/macOS. " +
                  "Supports ~ for home directory. Defaults to ~/.corretto_jdks.",
        ),
        "windows_base_path": attr.string(
            doc = "Base path where Corretto JDKs are installed on Windows. " +
                  "Supports ~ for home directory. Defaults to ~/.corretto_jdks.",
        ),
    },
)

local_corretto_toolchains = module_extension(
    implementation = _local_corretto_toolchains_impl,
    tag_classes = {"config": _config_tag},
)
