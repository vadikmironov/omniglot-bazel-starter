load("@gazelle//:def.bzl", "gazelle_binary")
load("@rules_go//go:def.bzl", "go_library", "go_test")

# Gazelle language extension that emits :publish targets. See lang.go
# for the extension's contract and behaviour.
go_library(
    name = "publish_lang",
    srcs = [
        "config.go",
        "generate.go",
        "kinds.go",
        "lang.go",
    ],
    importpath = "omniglot-bazel-starter/tools/publish/gazelle",
    visibility = ["//visibility:public"],
    deps = [
        "//tools/gazelle/directives",
        "@com_github_burntsushi_toml//:toml",
        "@gazelle//config",
        "@gazelle//label",
        "@gazelle//language",
        "@gazelle//repo",
        "@gazelle//resolve",
        "@gazelle//rule",
    ],
)

# Standalone gazelle binary scoped to our publish extension, plus the
# generation-free vocab extension so this binary recognises sibling
# generators' directives (lint_*) instead of warning on them. vocab owns
# no kinds and emits no rules, so it cannot affect publish generation.
# Invoked via `gazelle(..., gazelle = ":gazelle_publish")` in //BUILD.
gazelle_binary(
    name = "gazelle_publish",
    languages = [
        ":publish_lang",
        "//tools/gazelle/vocab",
    ],
    visibility = ["//visibility:public"],
)

# Internal-package tests for the publish_lang extension. embed = [:publish_lang]
# gives the tests access to unexported helpers (imageFormulas table, the
# resolve/validate functions in config.go) without having to widen them
# to package-public visibility.
go_test(
    name = "publish_lang_test",
    size = "small",
    srcs = ["generate_test.go"],
    embed = [":publish_lang"],
)
