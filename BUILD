# --- BEGIN lang:core ---
load("@buildifier_prebuilt//:rules.bzl", "buildifier")
# --- END lang:core ---

# --- BEGIN feature:publish,lint ---
load("@gazelle//:def.bzl", "gazelle")
# --- END feature:publish,lint ---

# --- BEGIN feature:lint ---
load("@rules_go//go:def.bzl", "nogo")
# --- END feature:lint ---

# --- BEGIN lang:core ---
package(default_visibility = ["//visibility:public"])

# --- BEGIN user-managed ---
# Repo-specific Bazel/Gazelle customizations — preserved across re-bootstrap.
# Add gazelle:exclude directives and tweak the buildifier excludes here.
#
# NOTE: the buildifier_prebuilt macro joins exclude_patterns with `-o` and
# appends ONE trailing `-prune`; find binds that prune to only the last
# `-path`, so keep this to a single pattern if you need pruning to take effect.
_BUILDIFIER_EXCLUDES = ["./.git/*"]
# --- END user-managed ---

# Buildifier lints and autoformats bazel (Starlark) files.
#
# Mac/Linux: Use the bazel targets directly
#   bazel run //:buildifier.fix
#   bazel run //:buildifier.check
#
# Windows: The macro has compatibility issues, use the wrapper script instead
#   tools\buildifier.bat fix
#   tools\buildifier.bat check
#
# See [tools/buildifier.md](tools/buildifier.md) for details on the Windows workaround.

buildifier(
    name = "buildifier.check",
    exclude_patterns = _BUILDIFIER_EXCLUDES,
    lint_mode = "warn",
    mode = "diff",
)

buildifier(
    name = "buildifier.fix",
    exclude_patterns = _BUILDIFIER_EXCLUDES,
    lint_mode = "fix",
    mode = "fix",
)

# rules_lint integration - export linter configurations
alias(
    name = "format",
    actual = "//tools/format",
)
# --- END lang:core ---

# --- BEGIN lang:cpp ---
exports_files(
    [".clang-tidy"],
    visibility = ["//visibility:public"],
)
# --- END lang:cpp ---

# --- BEGIN lang:rust ---
exports_files(
    [
        ".rustfmt.toml",
        ".clippy.toml",
    ],
    visibility = ["//visibility:public"],
)
# --- END lang:rust ---

# --- BEGIN feature:lint lang:java ---
# PMD / SpotBugs rulesets, consumed by the Java lint aspects in tools/lint.
exports_files(
    [
        ".pmd.xml",
        ".spotbugs-exclude.xml",
    ],
    visibility = ["//visibility:public"],
)
# --- END feature:lint lang:java ---

# --- BEGIN feature:lint lang:python ---
# Config files for the Python lint aspects, exported so the ruff and ty aspects
# (and the formatter, which reads the file directly) can reference them.
exports_files(
    [
        ".ruff.toml",
        "ty.toml",
    ],
    visibility = ["//visibility:public"],
)
# --- END feature:lint lang:python ---

# --- BEGIN lang:go ---
# rules_go configuration

# Go module definition exported for use in go_segment.MODULE.bazel.
# Reference: https://go.dev/doc/modules/gomod-ref
exports_files(["go.mod"])
# --- END lang:go ---

# --- BEGIN feature:lint ---
# Static analysis tool for Go code (nogo; part of the lint feature). Registered
# via go_sdk.nogo in tools/go/go_segment.MODULE.bazel.
# Reference: https://github.com/bazel-contrib/rules_go/blob/master/go/nogo.rst
nogo(
    name = "omniglot-bazel-starter_nogo",
    config = ":.nogo_config.json",
    vet = True,
    visibility = ["//visibility:public"],
)
# --- END feature:lint ---

# --- BEGIN feature:publish ---
exports_files(
    [".publish.toml"],
    visibility = ["//tools/publish:__subpackages__"],
)

# Gazelle driver for the publish extension. Auto-generates :publish
# targets from BUILD-file conventions (see tools/publish/gazelle/).
# CI enforces convergence via -publish_strict + `git diff --exit-code`.
#   bazel run //:publish_gen                  # apply
#   bazel run //:publish_gen -- -mode diff    # preview
#   bazel run //:publish_gen -- -publish_strict  # fail on convention violations
gazelle(
    name = "publish_gen",
    gazelle = "//tools/publish/gazelle:gazelle_publish",
)
# --- END feature:publish ---

# --- BEGIN feature:lint ---
# Gazelle driver for the lint extension. Auto-generates lint_test
# targets (ruff_test for py_*, etc.) tagged "lint" so CI can select
# them via `bazel test --test_tag_filters=lint //...`. See
# tools/lint/gazelle/.
#   bazel run //:lint_gen                  # apply
#   bazel run //:lint_gen -- -mode diff    # preview
gazelle(
    name = "lint_gen",
    gazelle = "//tools/lint/gazelle:gazelle_lint",
)
# --- END feature:lint ---
