load("@rules_java//java:defs.bzl", "java_binary")
load("//tools/java:package_defs.bzl", "log4j_build_deps", "wrap_build_deps")
load("//tools/lint:linters.bzl", "pmd_test", "spotbugs_test")
load("//tools/publish/lang:image_publish_defs.bzl", "image_publish")
load("//tools/publish/lang:java_publish_defs.bzl", "java_binary_publish")

package(default_visibility = ["//visibility:public"])

java_binary_publish(
    name = "publish",
    artifact_id = "java-app-with-ext-dep",
    binary_target = ":java_app_with_ext_dep",
)

java_binary(
    name = "java_app_with_ext_dep",
    srcs = glob(["src/**/*.java"]),
    main_class = "monorepo.example.Main",
    resources = ["src/main/resources/log4j2.properties"],
    deps = [] + log4j_build_deps() + wrap_build_deps([
        "org.jsoup:jsoup",
    ]),
)

pmd_test(
    name = "java_app_with_ext_dep.pmd_lint",
    size = "small",
    srcs = [":java_app_with_ext_dep"],
    tags = ["lint"],
)

spotbugs_test(
    name = "java_app_with_ext_dep.spotbugs_lint",
    size = "small",
    srcs = [":java_app_with_ext_dep"],
    tags = ["lint"],
)

image_publish(
    name = "publish_image",
    app_prefix = "app",
    artifact_id = "java-app-with-ext-dep",
    base = "@gcr_io_distroless_java17",
    binary_target = ":java_app_with_ext_dep_deploy.jar",
    entrypoint = [
        "java",
        "{runtime_args}",
        "-jar",
        "/app/java_app_with_ext_dep_deploy.jar",
    ],
    strip_prefix = "modules/java_app_with_ext_dep",
)
