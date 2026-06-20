# C++ App with External Dependencies

A `cc_binary` that uses `curl` and `libxml2` from the [Bazel Central Registry (BCR)](https://registry.bazel.build/), demonstrating how to manage third-party C++ dependencies in Bazel. Inspired by the [Googletest Bazel Quickstart](https://google.github.io/googletest/quickstart-bazel.html) and the [Abseil quickstart](https://abseil.io/docs/cpp/quickstart#set-up-a-bazel-workspace-to-work-with-abseil).

## Key BUILD Concepts

```bazel
load("@rules_cc//cc:defs.bzl", "cc_binary")

cc_binary(
    name = "cpp_app_with_ext_dep",
    srcs = ["src/main.cpp"],
    deps = [
        "@curl",
        "@libxml2",
    ],
)
```

BCR dependencies are referenced by their module name (e.g., `@curl`). The modules are declared in `tools/cpp/cpp_3rd_party_dependencies.MODULE.bazel`:

```bazel
bazel_dep(name = "curl", version = "8.11.0.bcr.4")
bazel_dep(name = "libxml2", version = "2.15.1")
```

## Adding New Dependencies

1. Find the library on [BCR](https://registry.bazel.build/)
2. Add `bazel_dep(name = "...", version = "...")` to `tools/cpp/cpp_3rd_party_dependencies.MODULE.bazel`
3. Use `@module_name` in your BUILD file's `deps`

## Building and Running

```bash
# Build the binary
bazel build //modules/cpp_app_with_ext_dep:cpp_app_with_ext_dep

# Run it
bazel run //modules/cpp_app_with_ext_dep:cpp_app_with_ext_dep
```

## When BCR Isn't Enough

BCR versions lag behind upstream and rely on community contributions. Some alternatives:

- **Custom module**: [This article](https://blog.andreiavram.ro/use-any-source-code-as-a-bazel-module/) explains how to use any source as a Bazel module. You can also [contribute version bumps](https://github.com/bazelbuild/bazel-central-registry/pulls) to BCR.

- **Conan integration**: [Conan + Bazel](https://docs.conan.io/2/examples/tools/google/bazeltoolchain/build_simple_bazel_7x_project.html) combines Conan's package management with Bazel builds.

- **rules_foreign_cc**: For libraries with CMake/Make build systems, [rules_foreign_cc](https://github.com/bazel-contrib/rules_foreign_cc) builds them within Bazel. See the [`cpp_app_with_cmake_dep`](../cpp_app_with_cmake_dep/README.md) sibling module for a worked example (building `fmt` from CMake), their [examples](https://github.com/bazel-contrib/rules_foreign_cc/tree/main/examples/third_party), and [this guide](https://hdlfactory.com/post/2023/06/13/how-to-use-the-make-rule-from-rules_foreign_cc-repository-for-bazel/).
