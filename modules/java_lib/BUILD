load("@rules_java//java:defs.bzl", "java_library")
load("//tools/java/testing:java_test_suite.bzl", "java_test_suite")
load("//tools/lint:linters.bzl", "pmd_test", "spotbugs_test")
load("//tools/publish/lang:java_publish_defs.bzl", "java_publish")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "java_lib",
    srcs = glob(["src/main/java/**/*.java"]),
    deps = [],
)

java_publish(
    name = "publish",
    artifact_id = "java-lib",
    library_target = ":java_lib",
)

java_test_suite(
    name = "java_lib_test",
    size = "small",
    srcs = glob(["src/test/java/**/*Test.java"]),
    deps = [
        "//modules/java_lib",
    ],
)

pmd_test(
    name = "java_lib.pmd_lint",
    size = "small",
    srcs = [":java_lib"],
    tags = ["lint"],
)

spotbugs_test(
    name = "java_lib.spotbugs_lint",
    size = "small",
    srcs = [":java_lib"],
    tags = ["lint"],
)
