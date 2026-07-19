"""Module extension that discovers a host-installed Go SDK, mirroring the
auto-discovery of the other host toolchains (//tools/cpp/toolchains:
host_cc_discovery.bzl, host_python_discovery.bzl, host_jdk_discovery.bzl).

Instead of pinning an SDK path and version, the repository rule enumerates
candidate GOROOTs (the GOROOT env var, `go` on PATH, and the children of the
conventional install roots below) and wires the newest valid SDK through
rules_go's SDK infrastructure, substituting @io_bazel_rules_go with @rules_go
for bzlmod compatibility. Install SDKs with
//tools/go/toolchains:host_go_sdk_setup.sh (default root ~/.go_sdks).

Unlike the other host toolchains, the @host_go_sdk toolchain is registered
globally (rules_go resolves the first matching toolchain, so an
--extra_toolchains config cannot outrank it), which is why activation is
gated by USE_HOST_GO_SDK=1 (set via --config=go_host): without the gate the
toolchain never matches and the hermetic SDK stays the default. Useful when
https://go.dev/dl is not accessible (e.g. behind an Artifactory caching
proxy) and the hermetic download cannot be used. Refresh after installing or
removing an SDK with `bazel fetch --configure --force`.
"""

# buildifier: disable=bzl-visibility
load("@rules_go//go/private:platforms.bzl", "GOARCH_CONSTRAINTS", "GOOS_CONSTRAINTS")

# Conventional install locations. Roots holding versioned SDKs (as laid out by
# host_go_sdk_setup.sh) have their children probed; a candidate may also be a
# GOROOT itself (/usr/local/go).
_DEFAULT_SEARCH_PATHS = [
    "~/.go_sdks",  # host_go_sdk_setup.sh default root
    "/usr/local/go",  # official tarball instructions
    "/usr/lib/go",  # distro packages
]

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

def _read_sdk_version(ctx, goroot):
    """Returns the SDK version ("1.26.5") from VERSION or `go version`, or None."""
    version_file = goroot + "/VERSION"
    if ctx.path(version_file).exists:
        lines = ctx.read(version_file).splitlines()
        if lines and lines[0].startswith("go"):
            return lines[0][2:]
        return None

    result = ctx.execute([goroot + "/bin/go", "version"])
    if result.return_code != 0:
        return None
    parts = result.stdout.split(" ")
    if len(parts) > 2 and parts[2].startswith("go"):
        return parts[2][len("go"):]
    return None

def _version_key(version):
    """"1.26.5" -> [1, 26, 5] for elementwise comparison; tolerates rc/beta suffixes."""
    key = []
    for piece in version.split("."):
        digits = ""
        for ch in piece.elems():
            if not ch.isdigit():
                break
            digits += ch
        key.append(int(digits) if digits else 0)
    return key

def _local_sdk(ctx, path):
    """Symlink SDK contents to repository root."""
    for entry in ctx.path(path).readdir():
        if ctx.path(entry.basename).exists:
            continue
        ctx.symlink(entry, entry.basename)

# Placeholder BUILD file for a disabled or missing SDK - creates a toolchain
# that never matches, so resolution falls through to the hermetic SDK.
_PLACEHOLDER_BUILD_TEMPLATE = """
# Placeholder: host Go SDK discovery is disabled (USE_HOST_GO_SDK != 1) or no
# SDK was found. Install one with tools/go/toolchains/host_go_sdk_setup.sh and
# select it with --config=go_host.

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

def _expand_home_path(path, environ):
    """Expands a leading ~ to $HOME."""
    if path == "~" or path.startswith("~/"):
        home = environ.get("HOME", "/tmp")
        return home + path[1:]
    return path

def _discover_sdk(ctx):
    """Returns (goroot, version) of the newest valid SDK found, or (None, None)."""
    candidates = []

    goroot_env = ctx.os.environ.get("GOROOT")
    if goroot_env:
        candidates.append(goroot_env)

    go_bin = ctx.which("go")
    if go_bin != None:
        result = ctx.execute([str(go_bin), "env", "GOROOT"])
        if result.return_code == 0 and result.stdout.strip():
            candidates.append(result.stdout.strip())

    for root in ctx.attr.search_paths:
        root = _expand_home_path(root, ctx.os.environ)
        root_path = ctx.path(root)
        if not root_path.exists:
            continue
        if _is_valid_sdk(ctx, root):
            candidates.append(root)
        else:
            candidates.extend([str(child) for child in root_path.readdir()])

    best = None
    best_version = None
    best_key = None
    seen_realpaths = {}
    for candidate in candidates:
        if not _is_valid_sdk(ctx, candidate):
            continue
        realpath = str(ctx.path(candidate).realpath)
        if realpath in seen_realpaths:
            continue
        seen_realpaths[realpath] = True
        version = _read_sdk_version(ctx, realpath)
        if version == None:
            continue
        key = _version_key(version)
        if best == None or key > best_key:
            best, best_version, best_key = realpath, version, key
    return best, best_version

def _sdk_build_file(ctx, platform, version, experiments):
    """Generate BUILD.bazel from rules_go template with @rules_go substitution."""
    ctx.file("ROOT")
    goos, _, goarch = platform.partition("_")

    # Read the template from rules_go
    template_path = ctx.path(ctx.attr._sdk_build_file)
    template_content = ctx.read(template_path)

    # Substitute @io_bazel_rules_go with @rules_go for bzlmod compatibility.
    # rules_go's own SDK repos see that apparent name because they are created
    # by rules_go's extension; this repo is created by the root module's
    # extension, so labels resolve through the root's mapping instead.
    template_content = template_content.replace("@io_bazel_rules_go", "@rules_go")

    # The template delegates to define_sdk_repository_targets from
    # sdk_build_defs.bzl, whose macro body also spells labels with
    # @io_bazel_rules_go — and macro label strings resolve in the repo that
    # instantiates the rules (this one). Vendor a substituted copy into the
    # repo and point the template's load at it, so those labels resolve via
    # @rules_go too. Read at fetch time, so it tracks rules_go updates.
    defs_content = ctx.read(ctx.path(ctx.attr._sdk_build_defs))
    defs_content = defs_content.replace("@io_bazel_rules_go", "@rules_go")
    ctx.file("sdk_build_defs.bzl", defs_content, executable = False)
    template_content = template_content.replace(
        "load(\"@rules_go//go/private:sdk_build_defs.bzl\"",
        "load(\"//:sdk_build_defs.bzl\"",
    )

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
    # This allows register_toolchains("@host_go_sdk//:all") to work
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

def _host_go_sdk_impl(ctx):
    """Repository rule implementation for the discovered host Go SDK."""

    # Gate on the env var (set by --config=go_host) so the globally registered
    # toolchain stays a never-matching placeholder by default.
    if ctx.os.environ.get("USE_HOST_GO_SDK", "0") != "1":
        ctx.file("BUILD.bazel", _PLACEHOLDER_BUILD_TEMPLATE)
        return

    goroot, version = _discover_sdk(ctx)
    if goroot == None:
        # buildifier: disable=print
        print("WARNING: no host Go SDK found (searched GOROOT, PATH, {}). ".format(ctx.attr.search_paths) +
              "Install one with tools/go/toolchains/host_go_sdk_setup.sh; " +
              "falling back to the hermetic SDK.")
        ctx.file("BUILD.bazel", _PLACEHOLDER_BUILD_TEMPLATE)
        return

    platform = _detect_sdk_platform(ctx, goroot)
    _sdk_build_file(ctx, platform, version, ctx.attr.experiments)
    _local_sdk(ctx, goroot)

_host_go_sdk_rule = repository_rule(
    implementation = _host_go_sdk_impl,
    attrs = {
        "search_paths": attr.string_list(doc = "Roots or GOROOTs to probe for SDK installations"),
        "experiments": attr.string_list(doc = "Go experiments to enable via GOEXPERIMENT environment variable"),
        "_sdk_build_file": attr.label(
            default = "@rules_go//go/private:BUILD.sdk.bazel",
        ),
        "_sdk_build_defs": attr.label(
            default = "@rules_go//go/private:sdk_build_defs.bzl",
        ),
    },
    environ = ["USE_HOST_GO_SDK", "GOROOT", "PATH"],
    local = True,
    doc = "Creates a Go SDK repository from the newest discovered host installation",
)

_config_tag = tag_class(
    attrs = {
        "extra_search_paths": attr.string_list(
            doc = "Additional roots or GOROOTs to probe before the defaults " +
                  "(~/.go_sdks, /opt/go_sdk, /usr/local/go, /usr/lib/go).",
        ),
        "experiments": attr.string_list(
            doc = "Go experiments to enable via GOEXPERIMENT environment variable. " +
                  "Available experiments: https://github.com/golang/go/blob/master/src/internal/goexperiment/flags.go",
        ),
    },
    doc = "Optional tuning of host Go SDK discovery",
)

def _host_go_discovery_impl(module_ctx):
    """Creates the @host_go_sdk repository from the discovered host SDK."""
    extra_search_paths = []
    experiments = []
    for mod in module_ctx.modules:
        if not mod.is_root:
            continue
        for config in mod.tags.config:
            extra_search_paths.extend(config.extra_search_paths)
            experiments.extend(config.experiments)

    _host_go_sdk_rule(
        name = "host_go_sdk",
        search_paths = extra_search_paths + _DEFAULT_SEARCH_PATHS,
        experiments = experiments,
    )

    # Machine-local discovery: keep the result out of MODULE.bazel.lock.
    return module_ctx.extension_metadata(reproducible = True)

host_go_discovery = module_extension(
    implementation = _host_go_discovery_impl,
    tag_classes = {"config": _config_tag},
    doc = "Discovers the newest host Go SDK and wires it as a local toolchain.",
)
