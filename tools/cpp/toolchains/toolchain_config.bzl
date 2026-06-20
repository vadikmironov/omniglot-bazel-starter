"""
This toolchain configuration is to demonstrate creation of a toolchain configuration
for a local host compiler. Please see README.md for more information.
"""

load("@bazel_tools//tools/build_defs/cc:action_names.bzl", "ACTION_NAMES")
load("@bazel_tools//tools/cpp:cc_toolchain_config_lib.bzl", "feature", "flag_group", "flag_set", "tool_path")  # buildifier: disable=deprecated-function
load("@rules_cc//cc/common:cc_common.bzl", "cc_common")

GCC_HOST_LOCAL = "gcc_host_local"
CLANG_HOST_LOCAL = "clang_host_local"

COMPILER_PATH_PREFIX = {
    GCC_HOST_LOCAL: "/usr/bin/",
    CLANG_HOST_LOCAL: "/usr/bin/",
}

all_link_actions = [
    ACTION_NAMES.cpp_link_executable,
    ACTION_NAMES.cpp_link_dynamic_library,
    ACTION_NAMES.cpp_link_nodeps_dynamic_library,
]

def _impl(ctx):
    if ctx.attr.compiler_flavour_name not in COMPILER_PATH_PREFIX:
        fail("compiler_flavour_name must be set and registered in COMPILER_PATH_PREFIX dictionary.")

    tool_path_prefix = COMPILER_PATH_PREFIX[ctx.attr.compiler_flavour_name]

    tool_paths = []

    # for a proper way to calculate builtin_includes see here:
    # https://github.com/bazelbuild/rules_cc/blob/main/cc/private/toolchain/unix_cc_configure.bzl:configure_unix_toolchain (_get_cxx_include_directories use)
    # otherwise, you can do `gcc -print-prog-name=cc1` -v < /dev/null and `gcc -print-prog-name=cc1plus` -v < /dev/null to find out
    # or clang -E -x c - -v < /dev/null and clang++ -E -x c++ - -v < /dev/null for Clang
    builtin_include_directories = []

    link_libs = []

    if ctx.attr.compiler_flavour_name == GCC_HOST_LOCAL:
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
        builtin_include_directories = [
            "/usr/include/c++/14",
            "/usr/include/x86_64-linux-gnu/c++/14",
            "/usr/include/c++/14/backward",
            "/usr/lib/gcc/x86_64-linux-gnu/14/include",
            "/usr/local/include",
            "/usr/include/x86_64-linux-gnu",
            "/usr/include",
        ]

        link_libs = ["-lstdc++", "-lm"]
    elif ctx.attr.compiler_flavour_name == CLANG_HOST_LOCAL:
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
        builtin_include_directories = [
            "/usr/bin/../lib/gcc/x86_64-linux-gnu/12/../../../../include/c++/12",
            "/usr/bin/../lib/gcc/x86_64-linux-gnu/12/../../../../include/x86_64-linux-gnu/c++/12",
            "/usr/bin/../lib/gcc/x86_64-linux-gnu/12/../../../../include/c++/12/backward",
            "/usr/lib/llvm-19/lib/clang/19/include",
            "/usr/local/include",
            "/usr/include/x86_64-linux-gnu",
            "/usr/include",
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
    },
    provides = [CcToolchainConfigInfo],
)
