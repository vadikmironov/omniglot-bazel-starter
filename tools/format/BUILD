# --- BEGIN exclude ---
# The pmd/spotbugs lint tests below dogfood the (excluded) java-format_not_used
# wrapper; they sit in exclude markers so scaffolds never receive them.
# gazelle:lint_ignore_keep freezes this package so a repo-wide lint_gen won't
# regenerate them outside the markers. Remove the directive to regenerate.
# gazelle:lint_ignore_keep
# --- END exclude ---

# --- BEGIN lang:core ---
load("@aspect_rules_lint//format:defs.bzl", "format_multirun")

# --- END lang:core ---
# --- BEGIN exclude ---
load("@rules_java//java:defs.bzl", "java_binary")

# --- END exclude ---
# --- BEGIN lang:java ---
load("@rules_shell//shell:sh_binary.bzl", "sh_binary")

# --- END lang:java ---
# --- BEGIN exclude ---
load("//tools/java:package_defs.bzl", "wrap_build_deps")
# --- END exclude ---

# --- BEGIN exclude ---
# pmd_test/spotbugs_test below lint the (excluded) java-format_not_used wrapper —
# source-repo dogfooding only. Scaffolds get real lint tests from lint_gen.
load("//tools/lint:linters.bzl", "pmd_test", "spotbugs_test")
# --- END exclude ---

# --- BEGIN lang:core ---
#
# This BUILD file is derived from the aspect_rules_lint example:
# https://github.com/aspect-build/rules_lint/blob/main/example/tools/format/BUILD.bazel
#
# --- END lang:core ---

# --- BEGIN exclude ---
# Java format via aspect_rules_lint by default uses the google-java-format package:
# https://github.com/google/google-java-format
#
# Surprizingly, google-java-format is extremely limited in its configuration options and
# even more surprizing is that it does not support much of configuration options anyway.
# palantir-java-format is a fork of google-java-format that adds a more sensible palantir
# default mode which at least does not look alien in java world.
#
# More on the sad story of java formatters can be found here:
# https://jqno.nl/post/2024/08/24/why-are-there-no-decent-code-formatters-for-java/
java_binary(
    name = "java-format_not_used",
    srcs = glob(["src/main/java/**/*.java"]),
    jvm_flags = [
        "--add-exports jdk.compiler/com.sun.tools.javac.api=ALL-UNNAMED",
        "--add-exports jdk.compiler/com.sun.tools.javac.file=ALL-UNNAMED",
        "--add-exports jdk.compiler/com.sun.tools.javac.parser=ALL-UNNAMED",
        "--add-exports jdk.compiler/com.sun.tools.javac.tree=ALL-UNNAMED",
        "--add-exports jdk.compiler/com.sun.tools.javac.util=ALL-UNNAMED",
    ],
    main_class = "monorepo.test.PalantirJavaFormatWrapper",
    deps = [] + wrap_build_deps([
        "com.palantir.javaformat:palantir-java-format",
    ]),
)
# --- END exclude ---

# --- BEGIN lang:java ---
sh_binary(
    name = "java-format_clang_format_wrapper",
    srcs = ["src/main/shell/clang_format_adapter_for_aspect_lint_java.sh"],
    data = [
        "@llvm_toolchain_llvm//:bin/clang-format",
    ],
    deps = [
        "@rules_shell//shell/runfiles",
    ],
)
# --- END lang:java ---

# --- BEGIN lang:core ---
# see an example of a format_multirun for all supported languages here:
# https://github.com/aspect-build/rules_lint/blob/main/example/tools/format/BUILD.bazel#L66
format_multirun(
    name = "format",
    # --- END lang:core ---
    # --- BEGIN lang:cpp ---
    c = "@llvm_toolchain_llvm//:bin/clang-format",
    cc = "@llvm_toolchain_llvm//:bin/clang-format",
    # --- END lang:cpp ---
    # --- BEGIN lang:go ---
    go = "@aspect_rules_lint//format:gofumpt",
    # --- END lang:go ---
    # --- BEGIN exclude ---
    #
    # Please see above the definition of :java-format_not_used rule and reasons why
    # default java formatter from aspect_rules_lint is not used.
    #
    #java = ":java-format_not_used",
    #
    # clang-format is used instead to format java and a simple shell wrapper translates
    # rules_lint command line arguments to what clang-format expects.
    #
    # --- END exclude ---
    # --- BEGIN lang:java ---
    java = ":java-format_clang_format_wrapper",
    # --- END lang:java ---
    # --- BEGIN lang:python ---
    python = "@aspect_rules_lint//format:ruff",
    # --- END lang:python ---
    # --- BEGIN lang:rust ---
    rust = "@rules_rust//tools/upstream_wrapper:rustfmt",
    # --- END lang:rust ---
    # --- BEGIN lang:core ---
    visibility = ["//visibility:public"],
)
# --- END lang:core ---

# --- BEGIN exclude ---
pmd_test(
    name = "java-format_not_used.pmd_lint",
    size = "small",
    srcs = [":java-format_not_used"],
    tags = ["lint"],
)

spotbugs_test(
    name = "java-format_not_used.spotbugs_lint",
    size = "small",
    srcs = [":java-format_not_used"],
    tags = ["lint"],
)
# --- END exclude ---
