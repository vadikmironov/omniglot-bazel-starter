load("@rules_java//java:defs.bzl", "java_binary")
load("//tools/lint:linters.bzl", "pmd_test", "spotbugs_test")
load("//tools/publish/lang:image_publish_defs.bzl", "image_publish")
load("//tools/publish/lang:java_publish_defs.bzl", "java_binary_publish")

package(default_visibility = ["//visibility:public"])

java_binary_publish(
    name = "publish",
    artifact_id = "java-app",
    binary_target = ":java_app",
)

java_binary(
    name = "java_app",
    srcs = glob(["src/**/*.java"]),
    main_class = "monorepo.example.Main",
    deps = ["//modules/java_lib"],
)

pmd_test(
    name = "java_app.pmd_lint",
    size = "small",
    srcs = [":java_app"],
    tags = ["lint"],
)

spotbugs_test(
    name = "java_app.spotbugs_lint",
    size = "small",
    srcs = [":java_app"],
    tags = ["lint"],
)

image_publish(
    name = "publish_image",
    app_prefix = "app",
    artifact_id = "java-app",
    base = "@gcr_io_distroless_java17",
    binary_target = ":java_app_deploy.jar",
    entrypoint = [
        "java",
        "{runtime_args}",
        "-jar",
        "/app/java_app_deploy.jar",
    ],
    strip_prefix = "modules/java_app",
)
