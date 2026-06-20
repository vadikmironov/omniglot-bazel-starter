# C++ Toolchains

This directory contains non-hermetic C++ toolchain configurations that use system-installed GCC or Clang compilers. These complement the default [toolchains_llvm](https://github.com/bazel-contrib/toolchains_llvm) hermetic toolchain and demonstrate how to configure custom C++ toolchains in Bazel.

Based on the [Bazel C++ Toolchain Tutorial](https://bazel.build/tutorials/ccp-toolchain-config) and the [rules_cc minimal example](https://github.com/bazelbuild/rules_cc/blob/main/examples/custom_toolchain/toolchain_config.bzl).

## Quick Start

These toolchains use compilers already installed on your system (`gcc`/`g++` or `clang`/`clang++`).

```bash
# Build with system GCC
bazel build --config=gcc_host //modules/cpp_app

# Build with system Clang
bazel build --config=clang_host //modules/cpp_app

# Debug toolchain resolution
bazel build --config=gcc_host_debug //modules/cpp_app
```

## Available .bazelrc Configurations

```bash
--config=gcc_host        # Use system GCC (non-hermetic)
--config=clang_host      # Use system Clang (non-hermetic)
--config=gcc_host_debug  # GCC with toolchain resolution debugging
```

## Hermetic toolchains (the production defaults)

The configs above are **non-hermetic examples** — they rely on whatever `gcc`/`clang` is
installed on the host. For reproducible builds the repo ships two hermetic toolchains, wired
as core C++ dependencies (not gated behind the `custom_toolchains` feature, so they survive a
bootstrap that drops this directory):

- **Hermetic LLVM/Clang** ([toolchains_llvm](https://github.com/bazel-contrib/toolchains_llvm)) —
  the default; no flag needed.
- **Hermetic GCC** ([gcc-toolchain](https://github.com/f0rmiga/gcc-toolchain), pinned GCC 15.2.0) —
  opt in with `--config=gcc_hermetic` (or `--config=gcc_hermetic_debug` for resolution debugging).
