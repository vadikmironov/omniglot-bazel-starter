load("@rules_cc//cc:defs.bzl", "cc_binary", "cc_library", "cc_test")
load("//tools/lint:linters.bzl", "clang_tidy_test")

# gazelle:publish_ignore
# gazelle:profiling

package(default_visibility = ["//visibility:public"])

cc_library(
    name = "cpp_workloads",
    srcs = glob(["src/**/*.cpp"]),
    hdrs = glob(["include/**/*.h"]),
    includes = ["include"],
)

cc_test(
    name = "cpp_workloads_test",
    size = "small",
    srcs = glob(["tests/**/*.cpp"]),
    linkstatic = True,
    deps = [
        ":cpp_workloads",
        "@googletest//:gtest",
        "@googletest//:gtest_main",
    ],
)

cc_binary(
    name = "bench_matmul",
    srcs = [
        "benches/bench_matmul.cpp",
        "benches/prof_main.cpp",
    ],
    tags = ["profiling-cpu"],
    deps = [
        ":cpp_workloads",
        "@google_benchmark//:benchmark",
        "@gperftools//:cpu_profiler",
    ],
)

cc_binary(
    name = "bench_pointer_chase",
    srcs = [
        "benches/bench_pointer_chase.cpp",
        "benches/prof_main.cpp",
    ],
    tags = ["profiling-cpu"],
    deps = [
        ":cpp_workloads",
        "@google_benchmark//:benchmark",
        "@gperftools//:cpu_profiler",
    ],
)

cc_binary(
    name = "bench_quicksort",
    srcs = [
        "benches/bench_quicksort.cpp",
        "benches/prof_main.cpp",
    ],
    tags = ["profiling-cpu"],
    deps = [
        ":cpp_workloads",
        "@google_benchmark//:benchmark",
        "@gperftools//:cpu_profiler",
    ],
)

cc_binary(
    name = "mem_fragmentation",
    srcs = [
        "mem/mem_fragmentation.cpp",
        "mem/prof_dump.cpp",
        "mem/prof_dump.h",
    ],
    tags = ["profiling-mem"],
    deps = [
        ":cpp_workloads",
        "@gperftools//:tcmalloc",
    ],
)

cc_binary(
    name = "mem_retained_growth",
    srcs = [
        "mem/mem_retained_growth.cpp",
        "mem/prof_dump.cpp",
        "mem/prof_dump.h",
    ],
    tags = ["profiling-mem"],
    deps = [
        ":cpp_workloads",
        "@gperftools//:tcmalloc",
    ],
)

cc_binary(
    name = "mem_string_churn",
    srcs = [
        "mem/mem_string_churn.cpp",
        "mem/prof_dump.cpp",
        "mem/prof_dump.h",
    ],
    tags = ["profiling-mem"],
    deps = [
        ":cpp_workloads",
        "@gperftools//:tcmalloc",
    ],
)

clang_tidy_test(
    name = "cpp_workloads.lint",
    size = "small",
    srcs = [":cpp_workloads"],
    tags = ["lint"],
)

clang_tidy_test(
    name = "bench_matmul.lint",
    size = "small",
    srcs = [":bench_matmul"],
    tags = ["lint"],
)

clang_tidy_test(
    name = "bench_pointer_chase.lint",
    size = "small",
    srcs = [":bench_pointer_chase"],
    tags = ["lint"],
)

clang_tidy_test(
    name = "bench_quicksort.lint",
    size = "small",
    srcs = [":bench_quicksort"],
    tags = ["lint"],
)

clang_tidy_test(
    name = "mem_fragmentation.lint",
    size = "small",
    srcs = [":mem_fragmentation"],
    tags = ["lint"],
)

clang_tidy_test(
    name = "mem_retained_growth.lint",
    size = "small",
    srcs = [":mem_retained_growth"],
    tags = ["lint"],
)

clang_tidy_test(
    name = "mem_string_churn.lint",
    size = "small",
    srcs = [":mem_string_churn"],
    tags = ["lint"],
)
