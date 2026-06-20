load("@gazelle//:def.bzl", "gazelle_binary")
load("@rules_go//go:def.bzl", "go_library")

# Gazelle language extension that emits lint_test targets. See lang.go
# for the extension's contract and behaviour. Per-language generators
# in cpp.go, rust.go, java.go, python.go are wrapped in lang-segment
# markers so a scaffolded fork that omits a language compiles this
# extension with that language's generator absent.
go_library(
    name = "lint_lang",
    srcs = [
        "generate.go",
        "kinds.go",
        "lang.go",
        # --- BEGIN lang:cpp ---
        "cpp.go",
        # --- END lang:cpp ---
        # --- BEGIN lang:rust ---
        "rust.go",
        # --- END lang:rust ---
        # --- BEGIN lang:java ---
        "java.go",
        # --- END lang:java ---
        # --- BEGIN lang:python ---
        "python.go",
        # --- END lang:python ---
    ],
    importpath = "omniglot-bazel-starter/tools/lint/gazelle",
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

# Standalone gazelle binary scoped to our lint extension, plus the
# generation-free vocab extension so this binary recognises sibling
# generators' directives (publish_*) instead of warning on them. vocab
# owns no kinds and emits no rules, so it cannot affect lint generation.
# Invoked via `gazelle(..., gazelle = ":gazelle_lint")` in //BUILD.
gazelle_binary(
    name = "gazelle_lint",
    languages = [
        ":lint_lang",
        "//tools/gazelle/vocab",
    ],
    visibility = ["//visibility:public"],
)
