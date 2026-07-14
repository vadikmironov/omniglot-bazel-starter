load("@gazelle//:def.bzl", "gazelle_binary")
load("@rules_go//go:def.bzl", "go_library", "go_test")

# Gazelle language extension that generates profiling workload targets
# for packages opted in via # gazelle:profiling. See lang.go for the
# extension's contract. Per-language generators are wrapped in
# lang-segment markers so a scaffolded fork that omits a language
# compiles this extension with that language's generator absent.
go_library(
    name = "profiling_lang",
    srcs = [
        "generate.go",
        "kinds.go",
        "lang.go",
        # --- BEGIN lang:cpp ---
        "cpp.go",
        # --- END lang:cpp ---
        # --- BEGIN lang:go ---
        "go.go",
        # --- END lang:go ---
        # --- BEGIN lang:java ---
        "java.go",
        # --- END lang:java ---
        # --- BEGIN lang:python ---
        "python.go",
        # --- END lang:python ---
        # --- BEGIN lang:rust ---
        "rust.go",
        # --- END lang:rust ---
    ],
    importpath = "omniglot-bazel-starter/tools/profile/gazelle",
    visibility = ["//visibility:public"],
    deps = [
        "//tools/gazelle/directives",
        "@gazelle//config",
        "@gazelle//label",
        "@gazelle//language",
        "@gazelle//repo",
        "@gazelle//resolve",
        "@gazelle//rule",
    ],
)

# --- BEGIN lang:rust ---
# Internal-package tests for the profiling_lang extension; they exercise
# the rust generator, so they ship only with rust. embed gives the tests
# access to unexported helpers without widening visibility.
go_test(
    name = "profiling_lang_test",
    size = "small",
    srcs = ["generate_test.go"],
    embed = [":profiling_lang"],
)
# --- END lang:rust ---

# Standalone gazelle binary scoped to our profiling extension, plus the
# generation-free vocab extension so this binary recognises sibling
# generators' directives (lint_*, publish_*) instead of warning on them.
# Invoked via `gazelle(..., gazelle = ":gazelle_profiling")` in //BUILD.
gazelle_binary(
    name = "gazelle_profiling",
    languages = [
        ":profiling_lang",
        "//tools/gazelle/vocab",
    ],
    visibility = ["//visibility:public"],
)
