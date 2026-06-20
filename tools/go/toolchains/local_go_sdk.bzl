"""
Module extension to configure a local Go SDK installation for use with bzlmod.

This extension provides a bzlmod-compatible way to use a pre-installed Go SDK
from a local filesystem path. It reuses rules_go's SDK infrastructure but
substitutes @io_bazel_rules_go with @rules_go for bzlmod compatibility.
"""

# buildifier: disable=bzl-visibility
load("@rules_go//go/private:platforms.bzl", "GOARCH_CONSTRAINTS", "GOOS_CONSTRAINTS")

# Functions below are copied from rules_go as they are private. Source:
# https://github.com/bazel-contrib/rules_go/blob/master/go/private/sdk.bzl

def _detect_sdk_platform(ctx, goroot):
    """Detect the SDK platform by examining the Go SDK's tool directory structure."""
    path = ctx.path(goroot + "/pkg/tool")
    if not path.exists:
        fail("Could not detect SDK platform: failed to find " + str(path))
    tool_entries = path.readdir()

    platforms = []
    for f in tool_entries:
        if f.basename.find("_") >= 0:
            platforms.append(f.basename)

    if len(platforms) == 0:
        fail("Could not detect SDK platform: found no platforms in %s" % path)
    if len(platforms) > 1:
        fail("Could not detect SDK platform: found multiple platforms %s in %s" % (platforms, path))
    return platforms[0]

def _detect_sdk_version(ctx, goroot):
    """Detect the SDK version from VERSION file or go binary."""
    version_file_path = goroot + "/VERSION"
    if ctx.path(version_file_path).exists:
        version_line = ctx.read(version_file_path).splitlines()[0]
        version = version_line[2:] if version_line.startswith("go") else version_line
        if ctx.attr.version and ctx.attr.version != version:
            fail("SDK is version %s, but version %s was expected" % (version, ctx.attr.version))
        return version

    go_binary_path = goroot + "/bin/go"
    result = ctx.execute([go_binary_path, "version"])
    if result.return_code != 0:
        fail("Could not detect SDK version: '%s version' exited with code %d" % (go_binary_path, result.return_code))

    output_parts = result.stdout.split(" ")
    if len(output_parts) > 2 and output_parts[2].startswith("go"):
        version = output_parts[2][len("go"):]
    elif len(output_parts) > 3 and output_parts[2] == "devel" and output_parts[3].startswith("go"):
        version = output_parts[3][len("go"):]
    else:
        fail("Could not parse SDK version from '%s version' output: %s" % (go_binary_path, result.stdout))

    if ctx.attr.version and ctx.attr.version != version:
        fail("SDK is version %s, but version %s was expected" % (version, ctx.attr.version))
    return version

def _local_sdk(ctx, path):
    """Symlink SDK contents to repository root."""
    for entry in ctx.path(path).readdir():
        if ctx.path(entry.basename).exists:
            continue
        ctx.symlink(entry, entry.basename)

# End of copied functions from rules_go

# Placeholder BUILD file for missing SDK - creates toolchain that never matches
_PLACEHOLDER_BUILD_TEMPLATE = """
# Placeholder for missing or invalid local Go SDK installation at: {path}
# This placeholder allows the build to proceed when this toolchain is not selected.
# If you explicitly select this toolchain and the SDK is not installed, you will
# get a clear error message.

package(default_visibility = ["//visibility:public"])

filegroup(
    name = "go_sdk",
    srcs = [],
)

# Toolchain that never matches due to impossible constraint
toolchain(
    name = "go_incompatible_toolchain",
    exec_compatible_with = ["@platforms//:incompatible"],
    target_compatible_with = ["@platforms//:incompatible"],
    toolchain = ":go_sdk",
    toolchain_type = "@rules_go//go:toolchain",
)
"""

def _is_valid_sdk(ctx, goroot):
    """Check if the path is a valid Go SDK installation."""
    if not ctx.path(goroot).exists:
        return False
    if not ctx.path(goroot + "/bin/go").exists:
        return False
    pkg_tool_path = ctx.path(goroot + "/pkg/tool")
    if not pkg_tool_path.exists:
        return False
    return True

def _sdk_build_file(ctx, platform, version, experiments):
    """Generate BUILD.bazel from rules_go template with @rules_go substitution."""
    ctx.file("ROOT")
    goos, _, goarch = platform.partition("_")

    # Read the template from rules_go
    template_path = ctx.path(ctx.attr._sdk_build_file)
    template_content = ctx.read(template_path)

    # Substitute @io_bazel_rules_go with @rules_go for bzlmod compatibility
    template_content = template_content.replace("@io_bazel_rules_go", "@rules_go")

    # Apply variable substitutions
    substitutions = {
        "{goos}": goos,
        "{goarch}": goarch,
        "{exe}": ".exe" if goos == "windows" else "",
        "{version}": version,
        "{experiments}": repr(experiments),
        "{exec_compatible_with}": repr([
            GOARCH_CONSTRAINTS[goarch],
            GOOS_CONSTRAINTS[goos],
        ]),
    }

    for key, value in substitutions.items():
        template_content = template_content.replace(key, value)

    # Append native toolchain() declaration for the host platform
    # This allows register_toolchains("@go_local_sdk//:all") to work
    toolchain_decl = """
# Native toolchain for Bazel toolchain resolution
toolchain(
    name = "go_{goos}_{goarch}_toolchain",
    exec_compatible_with = [
        "{goarch_constraint}",
        "{goos_constraint}",
    ],
    target_compatible_with = [],
    toolchain = ":go_{goos}_{goarch}-impl",
    toolchain_type = "@rules_go//go:toolchain",
)
""".format(
        goos = goos,
        goarch = goarch,
        goarch_constraint = GOARCH_CONSTRAINTS[goarch],
        goos_constraint = GOOS_CONSTRAINTS[goos],
    )

    template_content += toolchain_decl
    ctx.file("BUILD.bazel", template_content, executable = False)

def _go_local_sdk_impl(ctx):
    """Repository rule implementation for local Go SDK."""
    goroot = ctx.attr.path

    # Check if local SDK is enabled via environment variable (disabled by default)
    use_local_sdk = ctx.os.environ.get("USE_LOCAL_GO_SDK", "0")

    # Treat disabled SDK same as invalid SDK - both result in placeholder
    if use_local_sdk == "1" and _is_valid_sdk(ctx, goroot):
        # Valid and enabled SDK - detect platform and version, generate BUILD file
        platform = _detect_sdk_platform(ctx, goroot)
        version = _detect_sdk_version(ctx, goroot)
        _sdk_build_file(ctx, platform, version, ctx.attr.experiments)
        _local_sdk(ctx, goroot)
    else:
        # SDK disabled or doesn't exist/invalid - create placeholder with incompatible toolchain
        # Only warn when SDK is explicitly enabled but invalid/missing
        if use_local_sdk == "1":
            # buildifier: disable=print
            print("WARNING: Local Go SDK not found or invalid at '{}'. ".format(goroot) +
                  "Toolchain '{}' will be unavailable. ".format(ctx.attr.name))

        ctx.file("BUILD.bazel", _PLACEHOLDER_BUILD_TEMPLATE.format(path = goroot))

_go_local_sdk_rule = repository_rule(
    implementation = _go_local_sdk_impl,
    attrs = {
        "path": attr.string(mandatory = True, doc = "Path to local Go SDK"),
        "version": attr.string(doc = "Expected Go SDK version"),
        "experiments": attr.string_list(doc = "Go experiments to enable"),
        "_sdk_build_file": attr.label(
            default = "@rules_go//go/private:BUILD.sdk.bazel",
        ),
    },
    environ = ["USE_LOCAL_GO_SDK"],
    local = True,
    doc = "Creates a Go SDK repository from a local installation",
)

_local_sdk_tag = tag_class(
    attrs = {
        "name": attr.string(
            mandatory = True,
            doc = "Name for the SDK repository (e.g., 'go_local_sdk')",
        ),
        "path": attr.string(
            mandatory = True,
            doc = "Absolute path to the local Go SDK installation (must contain bin/go)",
        ),
        "version": attr.string(
            doc = "Expected Go version for validation (e.g., '1.26.4')",
        ),
        "experiments": attr.string_list(
            doc = "Go experiments to enable via GOEXPERIMENT environment variable",
        ),
    },
    doc = "Configures a local Go SDK from a filesystem path",
)

def _go_local_sdk_extension_impl(module_ctx):
    """Creates local Go SDK repositories for each configured SDK."""
    for mod in module_ctx.modules:
        if not mod.is_root:
            continue

        for local_sdk in mod.tags.define_local_sdk:
            _go_local_sdk_rule(
                name = local_sdk.name,
                path = local_sdk.path,
                version = local_sdk.version if local_sdk.version else None,
                experiments = local_sdk.experiments if local_sdk.experiments else [],
            )

go_local_sdk_ext = module_extension(
    implementation = _go_local_sdk_extension_impl,
    tag_classes = {
        "define_local_sdk": _local_sdk_tag,
    },
    doc = "Extension to configure local Go SDK installations for bzlmod",
)
