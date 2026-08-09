load("@rules_rust//rust:defs.bzl", "rust_library", "rust_test")

# --- BEGIN feature:lint ---
# The lint test below is gazelle-generated (bazel run //:lint_gen) but wrapped
# in feature:lint section markers so it drops out of non-lint scaffolds.
# gazelle:lint_ignore_keep freezes this package — lint_gen neither regenerates nor
# prunes here — so a repo-wide run won't disturb the gating. To refresh it,
# delete the directive line, run lint_gen, re-wrap the emitted rule in feature:lint
# markers, then restore this line.
# gazelle:lint_ignore_keep
load("//tools/lint:linters.bzl", "clippy_test")

# --- END feature:lint ---

# =========================================================================
# criterion_pprof — criterion Profiler backed by pprof-rs
#
# Referenced as a dep by every generated Rust bench target. pprof-rs ships
# an equivalent behind its own `criterion` feature; that feature depends on
# criterion 0.5, so keeping the hookup here leaves criterion free to move.
# =========================================================================

rust_library(
    name = "criterion_pprof",
    srcs = ["criterion_pprof.rs"],
    visibility = ["//visibility:public"],
    deps = [
        "@crates//:criterion",
        "@crates//:pprof",
    ],
)

rust_test(
    name = "criterion_pprof_test",
    size = "small",
    srcs = ["criterion_pprof_test.rs"],
    deps = [
        ":criterion_pprof",
        "@crates//:criterion",
        "@crates//:pprof",
    ],
)

# --- BEGIN feature:lint ---
clippy_test(
    name = "criterion_pprof.lint",
    size = "small",
    srcs = [":criterion_pprof"],
    tags = ["lint"],
)

clippy_test(
    name = "criterion_pprof_test.lint",
    size = "small",
    srcs = [":criterion_pprof_test"],
    tags = ["lint"],
)
# --- END feature:lint ---
