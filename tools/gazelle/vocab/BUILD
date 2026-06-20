load("@rules_go//go:def.bzl", "go_library")

# Generation-free Gazelle language that registers the repo-wide directive
# vocabulary (//tools/gazelle/directives) via KnownDirectives. Added to
# every gazelle_binary's `languages` so each generator recognises sibling
# generators' directives instead of warning on them. Owns no kinds and
# emits no rules — see vocab.go.
go_library(
    name = "vocab",
    srcs = ["vocab.go"],
    importpath = "omniglot-bazel-starter/tools/gazelle/vocab",
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
