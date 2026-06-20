# C++ App with a CMake Dependency

A `cc_binary` that links [{fmt}](https://github.com/fmtlib/fmt) built from its
own `CMakeLists.txt` via [rules_foreign_cc](https://github.com/bazel-contrib/rules_foreign_cc).
Unlike `cpp_app_with_ext_dep` (which pulls `curl`/`libxml2` as native Bazel
modules from the [BCR](https://registry.bazel.build/)), this example consumes a
library that only ships a CMake build — the common case when bringing an
existing CMake project into Bazel.

## Key BUILD Concepts

```bazel
load("@rules_cc//cc:defs.bzl", "cc_binary")
load("@rules_foreign_cc//foreign_cc:defs.bzl", "cmake")

cmake(
    name = "fmt",
    cache_entries = {
        "FMT_TEST": "OFF",
        "FMT_DOC": "OFF",
    },
    lib_source = "@fmt_src//:all_srcs",
    out_static_libs = ["libfmt.a"],
)

cc_binary(
    name = "cpp_app_with_cmake_dep",
    srcs = ["src/main.cpp"],
    deps = [":fmt"],
)
```

- `cmake()` runs `cmake` (and `ninja`) in a sandbox using the prebuilt,
  hermetic toolchains that `rules_foreign_cc` registers — no host `cmake`
  install is needed.
- `lib_source` points at a filegroup of the unpacked upstream source;
  `out_static_libs` names the archive CMake produces (`libfmt.a`).
- `cache_entries` are forwarded as `-D` flags to the CMake configure step (here,
  to skip fmt's test and doc targets).
- The rule exposes the build result as a `CcInfo`, so the consuming `cc_binary`
  lists `:fmt` in `deps` and links it exactly like a native `cc_library`.

## Where the Dependency Is Declared

`rules_foreign_cc` is declared in `tools/cpp/cpp_segment.MODULE.bazel`. The fmt
source is fetched as a plain `http_archive` in this module's own
`fmt.MODULE.bazel`, included from the root `MODULE.bazel`:

```bazel
http_archive = use_repo_rule("@bazel_tools//tools/build_defs/repo:http.bzl", "http_archive")

http_archive(
    name = "fmt_src",
    build_file_content = """\
filegroup(
    name = "all_srcs",
    srcs = glob(["**"]),
    visibility = ["//visibility:public"],
)
""",
    sha256 = "8b852bb5aa6e7d8564f9e81394055395dd1d1936d38dfd3a17792a02bebd7af0",
    strip_prefix = "fmt-12.2.0",
    urls = ["https://github.com/fmtlib/fmt/archive/refs/tags/12.2.0.tar.gz"],
)
```

The raw source archive is fetched on purpose — the BCR `@fmt` module is a native
Bazel `cc_library` and would not exercise the CMake build at all.

## Building and Running

```bash
# Build the binary (also builds fmt via CMake on first run)
bazel build //modules/cpp_app_with_cmake_dep:cpp_app_with_cmake_dep

# Run it
bazel run //modules/cpp_app_with_cmake_dep:cpp_app_with_cmake_dep
```

## Other Build Systems

`rules_foreign_cc` also provides `configure_make` (Autotools), `make`, `meson`,
and `ninja` rules following the same `lib_source` → `CcInfo` pattern. See the
[upstream examples](https://github.com/bazel-contrib/rules_foreign_cc/tree/main/examples).
