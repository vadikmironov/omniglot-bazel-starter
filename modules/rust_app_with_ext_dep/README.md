# Rust App with Crate Dependencies

A `rust_binary` that uses external crates (`reqwest`, `tokio`, `august`), demonstrating how to manage third-party Rust dependencies in Bazel. Inspired by [this Tweag blog post](https://www.tweag.io/blog/2023-07-27-building-rust-workspace-with-bazel/) and the [rules_rust examples](https://github.com/bazelbuild/rules_rust/tree/main/examples/bzlmod/all_crate_deps).

## Key BUILD Concepts

```bazel
load("@rules_rust//rust:defs.bzl", "rust_binary")

rust_binary(
    name = "rust_app_with_ext_dep",
    srcs = ["src/main.rs"],
    deps = [
        "@crates//:reqwest",
        "@crates//:tokio",
        "@crates//:august",
    ],
)
```

Crates are referenced via `@crates//:crate_name`. The `@crates` repository is generated from `tools/rust/Cargo.toml` using rules_rust's crate_universe.

## Adding New Dependencies

1. Add the crate to `tools/rust/Cargo.toml`:
   ```toml
   [dependencies]
   serde = { version = "1.0", features = ["derive"] }
   ```
2. Use `@crates//:serde` in your BUILD file's `deps`

Unlike Python or Java, no explicit lockfile regeneration step is needed—Bazel picks up Cargo.toml changes automatically.

## Building and Running

```bash
# Build the binary
bazel build //modules/rust_app_with_ext_dep:rust_app_with_ext_dep

# Run it
bazel run //modules/rust_app_with_ext_dep:rust_app_with_ext_dep
```
