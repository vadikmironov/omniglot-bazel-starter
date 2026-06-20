# Go App with External Dependencies

A `go_binary` that uses [golang.org/x/net/html](https://pkg.go.dev/golang.org/x/net/html) to fetch and parse HTML, demonstrating how to manage external Go module dependencies in Bazel via [Gazelle](https://github.com/bazel-contrib/bazel-gazelle).

## Key BUILD Concepts

```bazel
load("@rules_go//go:def.bzl", "go_binary")

go_binary(
    name = "go_app_with_ext_dep",
    srcs = ["src/main.go"],
    deps = [
        "@org_golang_x_net//html",
    ],
)
```

External modules are referenced by their Gazelle-generated repository name (e.g., `@org_golang_x_net`). The mapping from Go import paths to Bazel labels is managed automatically by the `go_deps` extension in [`go_segment.MODULE.bazel`](../../tools/go/go_segment.MODULE.bazel).

## Adding New Dependencies

```bash
# Add a new module
bazel run @rules_go//go -- get github.com/some/package@v1.2.3

# Update all dependencies
bazel run @rules_go//go -- get -u ./...
```

These commands update `go.mod`, `go.sum`, and run `bazel mod tidy` to sync the `use_repo()` statements automatically.

## Building and Running

```bash
bazel build //modules/go_app_with_ext_dep
bazel run //modules/go_app_with_ext_dep
```
