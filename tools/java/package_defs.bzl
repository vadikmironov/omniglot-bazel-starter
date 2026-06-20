"""
This module contains shortcut functions for java external package dependencies
managed via maven repository in java_segment.MODULE.bazel.
"""

load("@rules_jvm_external//:defs.bzl", "artifact")

#
# This is a constant for a name of project specific Maven repository that will
# not clash with other modules (specifically protobuf module). It is a string
# constant that any BUILD file can by loading this rule, but also java shard
# of MODULE.bazel can refer to the same constant by loading it as an extension.
#
PROJECT_REPOSITORY_NAME = "omniglot-bazel-starter_maven_dependencies"

#
# JUnit 5 dependencies (inspired by https://github.com/bazel-contrib/rules_jvm/blob/main/java/private/junit5.bzl)
# Currently not used as the rules_jvm:java_junit5_test is tricky to get to work.
# Potential improvement would be to either wait until rules_java will include
# JUnit 5 support or adopt https://github.com/junit-team/junit5-samples/tree/main/junit5-jupiter-starter-bazel
# into a workable solution.
#
def junit5_runtime_deps(repository_name = PROJECT_REPOSITORY_NAME):
    return [
        artifact("org.junit.jupiter:junit-jupiter-engine", repository_name),
        artifact("org.junit.platform:junit-platform-console", repository_name),
        artifact("org.junit.platform:junit-platform-launcher", repository_name),
        artifact("org.junit.platform:junit-platform-reporting", repository_name),
    ]

def junit5_build_deps(repository_name = PROJECT_REPOSITORY_NAME):
    return [
        artifact("org.junit.jupiter:junit-jupiter-engine", repository_name),
        artifact("org.junit.jupiter:junit-jupiter-api", repository_name),
    ]

def log4j_build_deps(repository_name = PROJECT_REPOSITORY_NAME):
    return [
        artifact("org.apache.logging.log4j:log4j-core", repository_name),
        artifact("org.apache.logging.log4j:log4j-api", repository_name),
        artifact("org.apache.logging.log4j:log4j-slf4j-impl", repository_name),
        artifact("org.apache.logging.log4j:log4j-slf4j2-impl", repository_name),
    ]

def wrap_build_deps(deps, repository_name = PROJECT_REPOSITORY_NAME):
    return [
        artifact(dep, repository_name)
        for dep in deps
    ]
