load("@rules_python//python:defs.bzl", "py_binary", "py_library", "py_test")
load("//tools/lint:linters.bzl", "ruff_test", "ty_test")

# gazelle:publish_ignore
# gazelle:profiling

package(default_visibility = ["//visibility:public"])

py_library(
    name = "python_workloads",
    srcs = glob(["src/**/*.py"]),
    imports = ["src"],
)

py_test(
    name = "python_workloads_test",
    timeout = "short",
    srcs = glob(["tests/**/*.py"]),
    main = "tests/test_workloads.py",
    deps = [":python_workloads"],
)

py_test(
    name = "bench_matmul",
    size = "medium",
    srcs = [
        "benches/bench_matmul.py",
        "benches/conftest.py",
        "benches/pytest_main.py",
    ],
    args = ["--benchmark-disable"],
    main = "benches/pytest_main.py",
    tags = ["profiling-cpu"],
    deps = [
        ":python_workloads",
        "@omniglot-bazel-starter_pip_dependencies//pyinstrument:pkg",
        "@omniglot-bazel-starter_pip_dependencies//pytest:pkg",
        "@omniglot-bazel-starter_pip_dependencies//pytest_benchmark:pkg",
    ],
)

py_test(
    name = "bench_pointer_chase",
    size = "medium",
    srcs = [
        "benches/bench_pointer_chase.py",
        "benches/conftest.py",
        "benches/pytest_main.py",
    ],
    args = ["--benchmark-disable"],
    main = "benches/pytest_main.py",
    tags = ["profiling-cpu"],
    deps = [
        ":python_workloads",
        "@omniglot-bazel-starter_pip_dependencies//pyinstrument:pkg",
        "@omniglot-bazel-starter_pip_dependencies//pytest:pkg",
        "@omniglot-bazel-starter_pip_dependencies//pytest_benchmark:pkg",
    ],
)

py_test(
    name = "bench_quicksort",
    size = "medium",
    srcs = [
        "benches/bench_quicksort.py",
        "benches/conftest.py",
        "benches/pytest_main.py",
    ],
    args = ["--benchmark-disable"],
    main = "benches/pytest_main.py",
    tags = ["profiling-cpu"],
    deps = [
        ":python_workloads",
        "@omniglot-bazel-starter_pip_dependencies//pyinstrument:pkg",
        "@omniglot-bazel-starter_pip_dependencies//pytest:pkg",
        "@omniglot-bazel-starter_pip_dependencies//pytest_benchmark:pkg",
    ],
)

py_binary(
    name = "mem_retained_growth",
    srcs = [
        "mem/mem_retained_growth.py",
        "mem/prof_dump.py",
    ],
    imports = ["mem"],
    main = "mem/mem_retained_growth.py",
    tags = ["profiling-mem"],
    deps = [
        ":python_workloads",
        "@omniglot-bazel-starter_pip_dependencies//memray:pkg",
    ],
)

py_binary(
    name = "mem_string_churn",
    srcs = [
        "mem/mem_string_churn.py",
        "mem/prof_dump.py",
    ],
    imports = ["mem"],
    main = "mem/mem_string_churn.py",
    tags = ["profiling-mem"],
    deps = [
        ":python_workloads",
        "@omniglot-bazel-starter_pip_dependencies//memray:pkg",
    ],
)

ruff_test(
    name = "python_workloads.lint",
    size = "small",
    srcs = [":python_workloads"],
    tags = ["lint"],
)

ruff_test(
    name = "mem_retained_growth.lint",
    size = "small",
    srcs = [":mem_retained_growth"],
    tags = ["lint"],
)

ruff_test(
    name = "mem_string_churn.lint",
    size = "small",
    srcs = [":mem_string_churn"],
    tags = ["lint"],
)

ty_test(
    name = "python_workloads.ty",
    size = "small",
    srcs = [":python_workloads"],
    tags = ["lint"],
)

ty_test(
    name = "mem_retained_growth.ty",
    size = "small",
    srcs = [":mem_retained_growth"],
    tags = ["lint"],
)

ty_test(
    name = "mem_string_churn.ty",
    size = "small",
    srcs = [":mem_string_churn"],
    tags = ["lint"],
)
