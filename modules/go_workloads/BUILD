load("@rules_go//go:def.bzl", "go_binary", "go_library", "go_test")

# gazelle:publish_ignore
# gazelle:profiling

package(default_visibility = ["//visibility:public"])

go_library(
    name = "go_workloads",
    srcs = glob(["src/**/*.go"]),
    importpath = "omniglot-bazel-starter/modules/go_workloads",
)

go_test(
    name = "go_workloads_test",
    size = "small",
    srcs = glob(["tests/**/*.go"]),
    embed = [":go_workloads"],
    deps = ["@com_github_stretchr_testify//assert"],
)

go_test(
    name = "bench_matmul",
    srcs = ["benches/bench_matmul_test.go"],
    embed = [":go_workloads"],
    tags = ["profiling-cpu"],
)

go_test(
    name = "bench_pointer_chase",
    srcs = ["benches/bench_pointer_chase_test.go"],
    embed = [":go_workloads"],
    tags = ["profiling-cpu"],
)

go_test(
    name = "bench_quicksort",
    srcs = ["benches/bench_quicksort_test.go"],
    embed = [":go_workloads"],
    tags = ["profiling-cpu"],
)

go_binary(
    name = "mem_retained_growth",
    srcs = [
        "mem/mem_retained_growth.go",
        "mem/prof_dump.go",
    ],
    tags = ["profiling-mem"],
    deps = [":go_workloads"],
)

go_binary(
    name = "mem_string_churn",
    srcs = [
        "mem/mem_string_churn.go",
        "mem/prof_dump.go",
    ],
    tags = ["profiling-mem"],
    deps = [":go_workloads"],
)
