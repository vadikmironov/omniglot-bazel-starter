load("@rules_rust//rust:defs.bzl", "rust_binary", "rust_library", "rust_test")
load("//tools/lint:linters.bzl", "clippy_test")

# gazelle:publish_ignore

package(default_visibility = ["//visibility:public"])

rust_binary(
    name = "bench_matmul",
    srcs = ["benches/bench_matmul.rs"],
    tags = ["profiling-cpu"],
    deps = [
        ":rust_workloads",
        "@crates//:criterion",
        "@crates//:pprof",
    ],
)

rust_binary(
    name = "bench_quicksort",
    srcs = ["benches/bench_quicksort.rs"],
    tags = ["profiling-cpu"],
    deps = [
        ":rust_workloads",
        "@crates//:criterion",
        "@crates//:pprof",
    ],
)

rust_binary(
    name = "bench_pointer_chase",
    srcs = ["benches/bench_pointer_chase.rs"],
    tags = ["profiling-cpu"],
    deps = [
        ":rust_workloads",
        "@crates//:criterion",
        "@crates//:pprof",
    ],
)

rust_binary(
    name = "mem_retained_growth",
    srcs = [
        "mem/mem_retained_growth.rs",
        "mem/prof_dump.rs",
    ],
    crate_root = "mem/mem_retained_growth.rs",
    tags = ["profiling-mem"],
    deps = [
        ":rust_workloads",
        "@crates//:jemalloc_pprof",
        "@crates//:tikv-jemallocator",
    ],
)

rust_binary(
    name = "mem_string_churn",
    srcs = [
        "mem/mem_string_churn.rs",
        "mem/prof_dump.rs",
    ],
    crate_root = "mem/mem_string_churn.rs",
    tags = ["profiling-mem"],
    deps = [
        ":rust_workloads",
        "@crates//:jemalloc_pprof",
        "@crates//:tikv-jemallocator",
    ],
)

rust_binary(
    name = "mem_fragmentation",
    srcs = [
        "mem/mem_fragmentation.rs",
        "mem/prof_dump.rs",
    ],
    crate_root = "mem/mem_fragmentation.rs",
    tags = ["profiling-mem"],
    deps = [
        ":rust_workloads",
        "@crates//:jemalloc_pprof",
        "@crates//:tikv-jemallocator",
    ],
)

rust_library(
    name = "rust_workloads",
    srcs = glob(["src/**/*.rs"]),
    crate_root = "src/rust_workloads.rs",
    deps = ["@crates//:rand"],
)

rust_test(
    name = "rust_workloads_test",
    timeout = "short",
    srcs = glob(["tests/**/*.rs"]),
    deps = [":rust_workloads"],
)

clippy_test(
    name = "bench_matmul.lint",
    size = "small",
    srcs = [":bench_matmul"],
    tags = ["lint"],
)

clippy_test(
    name = "bench_quicksort.lint",
    size = "small",
    srcs = [":bench_quicksort"],
    tags = ["lint"],
)

clippy_test(
    name = "bench_pointer_chase.lint",
    size = "small",
    srcs = [":bench_pointer_chase"],
    tags = ["lint"],
)

clippy_test(
    name = "mem_retained_growth.lint",
    size = "small",
    srcs = [":mem_retained_growth"],
    tags = ["lint"],
)

clippy_test(
    name = "mem_string_churn.lint",
    size = "small",
    srcs = [":mem_string_churn"],
    tags = ["lint"],
)

clippy_test(
    name = "mem_fragmentation.lint",
    size = "small",
    srcs = [":mem_fragmentation"],
    tags = ["lint"],
)

clippy_test(
    name = "rust_workloads.lint",
    size = "small",
    srcs = [":rust_workloads"],
    tags = ["lint"],
)

clippy_test(
    name = "rust_workloads_test.lint",
    size = "small",
    srcs = [":rust_workloads_test"],
    tags = ["lint"],
)
