# gazelle:lint_ignore
#
# This BUILD defines the linter-tool binaries themselves (pmd, spotbugs)
# as wrapper rules around prebuilt JARs. They carry no source files, so
# the spotbugs/pmd aspects produce no rules_lint_human output group, and
# any auto-generated lint_test would fail analysis. lint_ignore opts the
# entire package out.

# --- BEGIN lang:java ---
load("@rules_java//java:defs.bzl", "java_binary")
load("//tools/java:package_defs.bzl", "log4j_build_deps", "wrap_build_deps")
# --- END lang:java ---

# --- BEGIN lang:core ---
#
# This BUILD file is derived from the aspect_rules_lint example:
# https://github.com/aspect-build/rules_lint/blob/main/example/tools/lint/BUILD.bazel
#

package(default_visibility = ["//:__subpackages__"])

# --- END lang:core ---

# --- BEGIN lang:java ---
java_binary(
    name = "pmd",
    # In PMD 6.x, this was the main class:
    # main_class = "net.sourceforge.pmd.PMD",
    # It changed in version 7.0
    # https://docs.pmd-code.org/pmd-doc-7.0.0/pmd_userdocs_migrating_to_pmd7.html
    main_class = "net.sourceforge.pmd.cli.PmdCli",
    runtime_deps = [] + log4j_build_deps() + wrap_build_deps(
        [
            "net.sourceforge.pmd:pmd-core",
            "net.sourceforge.pmd:pmd-java",
            "net.sourceforge.pmd:pmd-cli",
        ],
    ),
)

java_binary(
    name = "spotbugs",
    jvm_flags = [
        "--add-exports jdk.compiler/com.sun.tools.javac.api=ALL-UNNAMED",
        "--add-exports jdk.compiler/com.sun.tools.javac.file=ALL-UNNAMED",
        "--add-exports jdk.compiler/com.sun.tools.javac.parser=ALL-UNNAMED",
        "--add-exports jdk.compiler/com.sun.tools.javac.tree=ALL-UNNAMED",
        "--add-exports jdk.compiler/com.sun.tools.javac.util=ALL-UNNAMED",
    ],
    main_class = "edu.umd.cs.findbugs.LaunchAppropriateUI",
    runtime_deps = [] + log4j_build_deps() + wrap_build_deps(
        [
            "com.github.spotbugs:spotbugs",
        ],
    ),
)
# --- END lang:java ---

# --- BEGIN lang:rust ---
# Assertion script for the native rules_rust clippy gate (see
# //tools/lint:linters.bzl clippy_test): fails when captured clippy output is
# non-empty.
exports_files(["clippy_assert_empty.sh"])
# --- END lang:rust ---
