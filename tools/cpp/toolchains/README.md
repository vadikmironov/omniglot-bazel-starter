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
--config=gcc_remote      # Downloaded pinned xPack GCC (non-hermetic linking)
--config=clang_remote    # Downloaded pinned hermetic-llvm minimal Clang (non-hermetic linking)
```

## Remote pinned compilers

`remote_cc_toolchains.bzl` adds a corretto-style middle tier between the host configs and
the hermetic defaults: a pinned vendor archive — [xPack GCC](https://github.com/xpack-dev-tools/gcc-xpack)
or the [hermetic-llvm](https://github.com/hermeticbuild/hermetic-llvm) "minimal" Clang
(~41 MB, also ships clang-tidy/clang-format/llvm-cov) — is downloaded with SHA256
verification on first use of its `--config` and wired through the same
`toolchain_config.bzl` as the host compilers. Neither archive carries a libc/sysroot, so
both compile and link against the host glibc: pinned compiler, host runtime. Use them when
the distro compiler is too old, or behind an artifact proxy where vendor downloads must be
mirrorable URLs.

Both vendors have fully hermetic upgrades worth adopting later: the
[`llvm` BCR module](https://registry.bazel.build/modules/llvm) (hermetic-llvm's zero-sysroot
cc_toolchain, ~50x smaller than the toolchains_llvm distribution) is a viable replacement for
toolchains_llvm once upstream `bazel coverage` support lands
([#675](https://github.com/hermeticbuild/hermetic-llvm/issues/675)), and xPack GCC could be
hardened the same way by pairing it with a minimal downloaded sysroot.

## Auto-discovery

No compiler version or include path is pinned here: `host_cc_discovery.bzl` probes the
installed `g++`/`clang++` at fetch time for their builtin include search directories and
tool location (mirroring rules_cc's `unix_cc_configure.bzl`), and `toolchain_config.bzl`
consumes the probed values. After upgrading a host compiler, refresh with
`bazel fetch --configure --force`. The same convention backs the host Python and Java toolchains
(`tools/python/toolchains/host_python_discovery.bzl`, `tools/java/toolchains/host_jdk_discovery.bzl`).

## Hermetic toolchains (the production defaults)

The configs above are **non-hermetic examples** — they rely on whatever `gcc`/`clang` is
installed on the host. For reproducible builds the repo ships two hermetic toolchains, wired
as core C++ dependencies (not gated behind the `custom_toolchains` feature, so they survive a
bootstrap that drops this directory):

- **Hermetic LLVM/Clang** ([toolchains_llvm](https://github.com/bazel-contrib/toolchains_llvm)) —
  the default; no flag needed.
- **Hermetic GCC** ([gcc-toolchain](https://github.com/f0rmiga/gcc-toolchain), pinned GCC 15.2.0) —
  opt in with `--config=gcc_hermetic` (or `--config=gcc_hermetic_debug` for resolution debugging).
