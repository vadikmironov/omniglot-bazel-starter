"""
This toolchain configuration is to demonstrate creation of a toolchain configuration
for a local host compiler. Please see README.md for more information.
"""

load("@bazel_tools//tools/build_defs/cc:action_names.bzl", "ACTION_NAMES")
load("@bazel_tools//tools/cpp:cc_toolchain_config_lib.bzl", "feature", "flag_group", "flag_set", "tool_path")  # buildifier: disable=deprecated-function
load("@rules_cc//cc/common:cc_common.bzl", "cc_common")
load("@rules_cc//cc/toolchains:cc_toolchain_config_info.bzl", "CcToolchainConfigInfo")

GCC_HOST_LOCAL = "gcc_host_local"
CLANG_HOST_LOCAL = "clang_host_local"

# Remote flavours: the same host-linked toolchains, but driven by a pinned
# compiler downloaded by remote_cc_toolchains.bzl instead of whatever the
# distro ships.
GCC_REMOTE_XPACK = "gcc_remote_xpack"
CLANG_REMOTE_LLVM = "clang_remote_llvm"

_GCC_FLAVOURS = [GCC_HOST_LOCAL, GCC_REMOTE_XPACK]
_CLANG_FLAVOURS = [CLANG_HOST_LOCAL, CLANG_REMOTE_LLVM]

_KNOWN_FLAVOURS = _GCC_FLAVOURS + _CLANG_FLAVOURS

all_link_actions = [
    ACTION_NAMES.cpp_link_executable,
    ACTION_NAMES.cpp_link_dynamic_library,
    ACTION_NAMES.cpp_link_nodeps_dynamic_library,
]

all_compile_actions = [
    ACTION_NAMES.preprocess_assemble,
    ACTION_NAMES.linkstamp_compile,
    ACTION_NAMES.c_compile,
    ACTION_NAMES.cpp_compile,
    ACTION_NAMES.cpp_header_parsing,
    ACTION_NAMES.cpp_module_compile,
    ACTION_NAMES.clif_match,
]

def _impl(ctx):
    if ctx.attr.compiler_flavour_name not in _KNOWN_FLAVOURS:
        fail("compiler_flavour_name must be one of %s." % _KNOWN_FLAVOURS)

    tool_path_prefix = ctx.attr.tool_bin_dir

    tool_paths = []

    # The builtin include dirs are probed from the installed compiler at fetch
    # time by //tools/cpp/toolchains:host_cc_discovery.bzl (mirroring rules_cc's
    # unix_cc_configure.bzl) and passed in via builtin_include_directories, so
    # the toolchain adapts to whatever gcc/clang version is on the host instead
    # of hardcoding version-specific paths.
    builtin_include_directories = ctx.attr.builtin_include_directories

    link_libs = []

    if ctx.attr.compiler_flavour_name in _GCC_FLAVOURS:
        tool_paths = [
            tool_path(name = "ar", path = tool_path_prefix + "ar"),
            tool_path(name = "compat-ld", path = tool_path_prefix + "ld"),
            tool_path(name = "cpp", path = tool_path_prefix + "g++"),
            tool_path(name = "dwp", path = tool_path_prefix + "dwp"),
            tool_path(name = "gcc", path = tool_path_prefix + "gcc"),
            tool_path(name = "gcov", path = tool_path_prefix + "gcov"),
            tool_path(name = "ld", path = tool_path_prefix + "ld"),
            tool_path(name = "nm", path = tool_path_prefix + "nm"),
            tool_path(name = "objcopy", path = tool_path_prefix + "objcopy"),
            tool_path(name = "objdump", path = tool_path_prefix + "objdump"),
            tool_path(name = "strip", path = tool_path_prefix + "strip"),
        ]

        # xPack's libstdc++ headers are newer than the distro's runtime .so, so
        # the remote flavour links its libstdc++ statically to avoid GLIBCXX
        # version errors at runtime (same trick as gcc_hermetic in .bazelrc).
        if ctx.attr.compiler_flavour_name == GCC_REMOTE_XPACK:
            link_libs = ["-l:libstdc++.a", "-lm"]
        else:
            link_libs = ["-lstdc++", "-lm"]
    elif ctx.attr.compiler_flavour_name in _CLANG_FLAVOURS:
        tool_paths = [
            tool_path(name = "ar", path = tool_path_prefix + "ar"),
            tool_path(name = "compat-ld", path = tool_path_prefix + "ld"),
            tool_path(name = "cpp", path = tool_path_prefix + "clang++"),
            tool_path(name = "dwp", path = tool_path_prefix + "dwp"),
            tool_path(name = "gcc", path = tool_path_prefix + "clang"),
            tool_path(name = "gcov", path = tool_path_prefix + "gcov"),
            tool_path(name = "ld", path = tool_path_prefix + "ld"),
            tool_path(name = "nm", path = tool_path_prefix + "nm"),
            tool_path(name = "objcopy", path = tool_path_prefix + "objcopy"),
            tool_path(name = "objdump", path = tool_path_prefix + "objdump"),
            tool_path(name = "strip", path = tool_path_prefix + "strip"),
        ]
        link_libs = ["-lstdc++", "-lm"]
        #link_libs = ["-lc++", "-lm", ]

    else:
        fail("Unable to create tool_paths/builtin include lists for unknown compiler flavour.")

    features = [
        feature(
            name = "default_linker_flags",
            enabled = True,
            flag_sets = [
                flag_set(
                    actions = all_link_actions,
                    flag_groups = ([
                        flag_group(
                            flags = link_libs,
                        ),
                    ]),
                ),
            ],
        ),
        # Opt-in support for --features=external_include_paths (set repo-wide in
        # .bazelrc): include external-repo headers via -isystem so their
        # diagnostics don't fail first-party -Werror builds. Hermetic toolchains
        # define this themselves; without it here the flag is silently inert on
        # these toolchains.
        feature(
            name = "external_include_paths",
            flag_sets = [
                flag_set(
                    actions = all_compile_actions,
                    flag_groups = [
                        flag_group(
                            flags = ["-isystem", "%{external_include_paths}"],
                            iterate_over = "external_include_paths",
                            expand_if_available = "external_include_paths",
                        ),
                    ],
                ),
            ],
        ),
    ]

    return cc_common.create_cc_toolchain_config_info(
        ctx = ctx,
        features = features,
        cxx_builtin_include_directories = builtin_include_directories,
        toolchain_identifier = ctx.attr.compiler_flavour_name,
        host_system_name = "local",
        target_system_name = "local",
        target_cpu = ctx.attr.compiler_flavour_name,
        target_libc = "unknown",
        compiler = ctx.attr.compiler_flavour_name,
        abi_version = "local",
        abi_libc_version = "local",
        tool_paths = tool_paths,
    )

cc_toolchain_config = rule(
    implementation = _impl,
    attrs = {
        "compiler_flavour_name": attr.string(
            mandatory = True,
            doc = "A flavour name for the compiler, e.g. 'gcc', 'clang'.",
        ),
        "tool_bin_dir": attr.string(
            default = "/usr/bin/",
            doc = "Directory (trailing slash) holding the compiler and binutils, " +
                  "probed from the host by host_cc_discovery.",
        ),
        "builtin_include_directories": attr.string_list(
            doc = "Compiler builtin include search dirs, probed from the host by " +
                  "host_cc_discovery. Empty means the compiler was not found at fetch time.",
        ),
    },
    provides = [CcToolchainConfigInfo],
)
