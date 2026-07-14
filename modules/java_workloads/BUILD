load("@rules_java//java:defs.bzl", "java_binary", "java_library")
load("//tools/java/testing:java_test_suite.bzl", "java_test_suite")
load("//tools/lint:linters.bzl", "pmd_test", "spotbugs_test")

# gazelle:publish_ignore
# gazelle:profiling

package(default_visibility = ["//visibility:public"])

java_library(
    name = "java_workloads",
    srcs = glob(["src/**/*.java"]),
)

java_test_suite(
    name = "java_workloads_test",
    size = "small",
    srcs = glob(["tests/**/*Test.java"]),
    package = "monorepo.workloads",
    deps = [":java_workloads"],
)

java_binary(
    name = "bench_matmul",
    srcs = ["benches/BenchMatmul.java"],
    main_class = "org.openjdk.jmh.Main",
    plugins = ["//tools/profile:jmh_annprocess"],
    tags = [
        "no-lint",
        "profiling-cpu",
    ],
    deps = [
        ":java_workloads",
        "@omniglot-bazel-starter_maven_dependencies//:org_openjdk_jmh_jmh_core",
    ],
)

java_binary(
    name = "bench_pointer_chase",
    srcs = ["benches/BenchPointerChase.java"],
    main_class = "org.openjdk.jmh.Main",
    plugins = ["//tools/profile:jmh_annprocess"],
    tags = [
        "no-lint",
        "profiling-cpu",
    ],
    deps = [
        ":java_workloads",
        "@omniglot-bazel-starter_maven_dependencies//:org_openjdk_jmh_jmh_core",
    ],
)

java_binary(
    name = "bench_quicksort",
    srcs = ["benches/BenchQuicksort.java"],
    main_class = "org.openjdk.jmh.Main",
    plugins = ["//tools/profile:jmh_annprocess"],
    tags = [
        "no-lint",
        "profiling-cpu",
    ],
    deps = [
        ":java_workloads",
        "@omniglot-bazel-starter_maven_dependencies//:org_openjdk_jmh_jmh_core",
    ],
)

java_binary(
    name = "mem_retained_growth",
    srcs = [
        "mem/MemRetainedGrowth.java",
        "mem/ProfDump.java",
    ],
    main_class = "monorepo.workloads.MemRetainedGrowth",
    tags = ["profiling-mem"],
    deps = [":java_workloads"],
)

java_binary(
    name = "mem_string_churn",
    srcs = [
        "mem/MemStringChurn.java",
        "mem/ProfDump.java",
    ],
    main_class = "monorepo.workloads.MemStringChurn",
    tags = ["profiling-mem"],
    deps = [":java_workloads"],
)

pmd_test(
    name = "java_workloads.pmd_lint",
    size = "small",
    srcs = [":java_workloads"],
    tags = ["lint"],
)

pmd_test(
    name = "mem_retained_growth.pmd_lint",
    size = "small",
    srcs = [":mem_retained_growth"],
    tags = ["lint"],
)

pmd_test(
    name = "mem_string_churn.pmd_lint",
    size = "small",
    srcs = [":mem_string_churn"],
    tags = ["lint"],
)

spotbugs_test(
    name = "java_workloads.spotbugs_lint",
    size = "small",
    srcs = [":java_workloads"],
    tags = ["lint"],
)

spotbugs_test(
    name = "mem_retained_growth.spotbugs_lint",
    size = "small",
    srcs = [":mem_retained_growth"],
    tags = ["lint"],
)

spotbugs_test(
    name = "mem_string_churn.spotbugs_lint",
    size = "small",
    srcs = [":mem_string_churn"],
    tags = ["lint"],
)
