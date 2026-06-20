load("@rules_go//go:def.bzl", "go_library")

# Single source of truth for the gazelle directive vocabulary shared
# across this repo's code generators (lint_gen, publish_gen, and any
# future generator). Directive names are grouped by feature and
# section-gated so a scaffolded fork that drops a feature strips its
# directives with it. See directives.go for the contract.
go_library(
    name = "directives",
    srcs = ["directives.go"],
    importpath = "omniglot-bazel-starter/tools/gazelle/directives",
    visibility = ["//visibility:public"],
)
