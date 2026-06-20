load("@rules_cc//cc:cc_binary.bzl", "cc_binary")
load("@rules_python//python:defs.bzl", "py_binary", "py_library", "py_test")
load("//tools/lint:linters.bzl", "clang_tidy_test", "ruff_test")
load("//tools/publish/lang:generic_publish_defs.bzl", "binary_bundle_publish")
load("//tools/publish/lang:image_publish_defs.bzl", "image_publish")

package(default_visibility = ["//visibility:public"])

binary_bundle_publish(
    name = "publish",
    artifact_id = "cpp-py-ext-module",
    binary_target = ":cpp_py_ext_module",
)

py_library(
    name = "cpp_py_ext_module_lib",
    srcs = glob(
        ["src/**/*.py"],
        exclude = ["src/**/__main__.py"],
    ),
    data = glob(["src/**/*.pyi"]),
    imports = ["src"],
    deps = [":_cpp_py_ext_module_impl_py_lib"],
)

py_binary(
    name = "cpp_py_ext_module",
    srcs = glob(["src/**/__main__.py"]),
    main = "__main__.py",
    deps = [":cpp_py_ext_module_lib"],
)

#
# Using cc_binary with linkshared = True for building Python extension module.
# This is the recommended approach to ensure proper linking of Python libraries
# on Windows. The cc_shared_library approach has known issues with transitive
# Python library dependencies on Windows.
#
# See: https://github.com/bazel-contrib/rules_python/issues/824
#
cc_binary(
    name = "_cpp_py_ext_module_impl_raw.so",
    srcs = glob(["src/**/*.cpp"]),
    # On macOS, Python extension modules must not link against libpython directly.
    # Instead, symbols are resolved at runtime when Python loads the extension.
    # See: https://blog.tim-smith.us/2015/09/python-extension-modules-os-x/
    linkopts = select({
        "@platforms//os:macos": [
            "-undefined",
            "dynamic_lookup",
        ],
        "//conditions:default": [],
    }),
    linkshared = True,
    deps = [
        "//modules/cpp_library",
        "@rules_python//python/cc:current_py_cc_headers",
    ] + select({
        # On Windows, must link against Python library explicitly
        "@platforms//os:windows": ["@rules_python//python/cc:current_py_cc_libs"],
        "//conditions:default": [],
    }),
)

# On Windows, Python extension modules must use .pyd extension
genrule(
    name = "_cpp_py_ext_module_impl_pyd",
    srcs = [":_cpp_py_ext_module_impl_raw.so"],
    outs = ["cpp_py_ext_module_impl.pyd"],
    cmd = "cp $< $@",
)

# On non-Windows platforms, .so extension is used
genrule(
    name = "_cpp_py_ext_module_impl_so",
    srcs = [":_cpp_py_ext_module_impl_raw.so"],
    outs = ["cpp_py_ext_module_impl.so"],
    cmd = "cp $< $@",
)

alias(
    name = "_cpp_py_ext_module_impl",
    actual = select({
        "@platforms//os:windows": ":_cpp_py_ext_module_impl_pyd",
        "//conditions:default": ":_cpp_py_ext_module_impl_so",
    }),
)

#
# Intermediate py_library is not mandatory, but would be helpful if multiple
# packages would depend on it (py_test + actual python application target).
# If there is no need for it, data and imports sections can be embedded directly
# into py_test target.
#
py_library(
    name = "_cpp_py_ext_module_impl_py_lib",
    data = [
        "src/cpp_py_ext_module_impl.pyi",
        ":_cpp_py_ext_module_impl",
    ],
    imports = ["."],
)

py_test(
    name = "cpp_py_ext_module_test",
    timeout = "short",
    srcs = glob(["tests/**/*.py"]),
    main = "test_cpp_py_ext_module.py",
    deps = [":cpp_py_ext_module_lib"],
)

ruff_test(
    name = "cpp_py_ext_module_lib.lint",
    size = "small",
    srcs = [":cpp_py_ext_module_lib"],
    tags = ["lint"],
)

ruff_test(
    name = "cpp_py_ext_module.lint",
    size = "small",
    srcs = [":cpp_py_ext_module"],
    tags = ["lint"],
)

ruff_test(
    name = "_cpp_py_ext_module_impl_py_lib.lint",
    size = "small",
    srcs = [":_cpp_py_ext_module_impl_py_lib"],
    tags = ["lint"],
)

clang_tidy_test(
    name = "_cpp_py_ext_module_impl_raw.so.lint",
    size = "small",
    srcs = [":_cpp_py_ext_module_impl_raw.so"],
    tags = ["lint"],
)

image_publish(
    name = "publish_image",
    app_prefix = "app",
    artifact_id = "cpp-py-ext-module",
    base = "@gcr_io_distroless_python3",
    binary_target = ":cpp_py_ext_module",
    entrypoint = ["/app/cpp_py_ext_module"],
    strip_prefix = "modules/cpp_py_ext_module",
)
