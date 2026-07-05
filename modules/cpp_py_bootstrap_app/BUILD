# gazelle:publish_ignore

load("@rules_cc//cc:cc_binary.bzl", "cc_binary")
load("@rules_cc//cc:cc_library.bzl", "cc_library")
load("@rules_cc//cc:cc_test.bzl", "cc_test")
load("@rules_python//python:py_library.bzl", "py_library")
load("//tools/lint:linters.bzl", "clang_tidy_test", "ruff_test", "ty_test")
load(":python_interpreter_path_header.bzl", "python_interpreter_path_header")

package(default_visibility = ["//visibility:public"])

python_interpreter_path_header(
    name = "_cpp_py_bootstrap_app_python_interpreter_path_header",
)

cc_library(
    name = "_cpp_py_bootstrap_app_python_interpreter_path_header_lib",
    hdrs = [":_cpp_py_bootstrap_app_python_interpreter_path_header"],
    includes = ["."],
)

cc_library(
    name = "_cpp_py_bootstrap_app_lib",
    srcs = glob(
        ["src/**/*.cpp"],
        allow_empty = True,
        exclude = ["src/main.cpp"],
    ),
    hdrs = glob(
        ["include/**/*.h"],
        allow_empty = True,
    ),
    includes = ["include"],
    deps = [
        "@bazel_tools//tools/cpp/runfiles",
        "@rules_python//python/cc:current_py_cc_headers",
        "@rules_python//python/cc:current_py_cc_libs",
        "@spdlog",
    ],
)

cc_binary(
    name = "cpp_py_bootstrap_app",
    srcs = ["src/main.cpp"],
    data = [
        "//modules/python_lib",
        "@rules_python//python:current_py_toolchain",
    ],
    visibility = ["//visibility:public"],
    deps = [
        ":_cpp_py_bootstrap_app_lib",
        ":_cpp_py_bootstrap_app_python_interpreter_path_header_lib",
        "@bazel_tools//tools/cpp/runfiles",
        "@rules_python//python/cc:current_py_cc_headers",
        "@rules_python//python/cc:current_py_cc_libs",
        "@spdlog",
    ],
)

py_library(
    name = "_cpp_py_bootstrap_app_py_test_lib",
    testonly = True,
    srcs = glob(["tests/py_test_lib/**/*.py"]),
    imports = ["tests"],
)

cc_library(
    name = "_cpp_py_bootstrap_app_test_utils",
    testonly = True,
    hdrs = ["tests/test_utils.h"],
    strip_include_prefix = "tests",
)

cc_test(
    name = "cpp_py_bootstrap_app_python_toolchain_resolver_test",
    size = "small",
    srcs = glob(
        ["tests/**/*.cpp"],
        exclude = [
            "tests/call_in_subinterpreter_test.cpp",
            "tests/py_object_guard_test.cpp",
            "tests/py_result_converter_test.cpp",
            "tests/python_test_main.cpp",
            "tests/sub_interpreter_guard_test.cpp",
        ],
    ),
    linkstatic = True,
    deps = [
        ":_cpp_py_bootstrap_app_lib",
        ":_cpp_py_bootstrap_app_test_utils",
        "@googletest//:gtest",
        "@googletest//:gtest_main",
        "@spdlog",
    ],
)

cc_test(
    name = "cpp_py_bootstrap_app_python_types_test",
    size = "small",
    srcs = [
        "tests/py_object_guard_test.cpp",
        "tests/py_result_converter_test.cpp",
        "tests/python_test_main.cpp",
        "tests/sub_interpreter_guard_test.cpp",
    ],
    data = [
        "@rules_python//python:current_py_toolchain",
    ],
    linkstatic = True,
    deps = [
        ":_cpp_py_bootstrap_app_lib",
        "@googletest//:gtest",
        "@rules_python//python/cc:current_py_cc_headers",
        "@rules_python//python/cc:current_py_cc_libs",
        "@spdlog",
    ],
)

cc_test(
    name = "cpp_py_bootstrap_app_call_in_subinterpreter_test",
    size = "small",
    srcs = ["tests/call_in_subinterpreter_test.cpp"],
    data = [
        ":_cpp_py_bootstrap_app_py_test_lib",
        "//modules/python_lib",
        "@rules_python//python:current_py_toolchain",
    ],
    linkstatic = True,
    deps = [
        ":_cpp_py_bootstrap_app_lib",
        ":_cpp_py_bootstrap_app_python_interpreter_path_header_lib",
        "@bazel_tools//tools/cpp/runfiles",
        "@googletest//:gtest",
        "@rules_python//python/cc:current_py_cc_headers",
        "@rules_python//python/cc:current_py_cc_libs",
        "@spdlog",
    ],
)

ruff_test(
    name = "_cpp_py_bootstrap_app_py_test_lib.lint",
    size = "small",
    srcs = [":_cpp_py_bootstrap_app_py_test_lib"],
    tags = ["lint"],
)

clang_tidy_test(
    name = "_cpp_py_bootstrap_app_python_interpreter_path_header_lib.lint",
    size = "small",
    srcs = [":_cpp_py_bootstrap_app_python_interpreter_path_header_lib"],
    tags = ["lint"],
)

clang_tidy_test(
    name = "_cpp_py_bootstrap_app_lib.lint",
    size = "small",
    srcs = [":_cpp_py_bootstrap_app_lib"],
    tags = ["lint"],
)

clang_tidy_test(
    name = "cpp_py_bootstrap_app.lint",
    size = "small",
    srcs = [":cpp_py_bootstrap_app"],
    tags = ["lint"],
)

clang_tidy_test(
    name = "_cpp_py_bootstrap_app_test_utils.lint",
    size = "small",
    srcs = [":_cpp_py_bootstrap_app_test_utils"],
    tags = ["lint"],
)

ty_test(
    name = "_cpp_py_bootstrap_app_py_test_lib.ty",
    size = "small",
    srcs = [":_cpp_py_bootstrap_app_py_test_lib"],
    tags = ["lint"],
)
