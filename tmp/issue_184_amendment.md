The default C++ toolchain is `toolchains_llvm` with the official LLVM release tarball. Two problems follow from that choice.

## Challenge

**Size.** The 22.1.8 tarball is ~1.9 GB to download and **12 GB extracted** (8.9 GB of it `bin/`, 2.3 GB `lib/`). Every CI job that touches C++, and every contributor's first build, pays for it. We use clang, clang-tidy, clang-format, lld, llvm-symbolizer and llvm-cov; the rest of the release is dead weight.

**Two platforms missing.** Both follow from what the official release publishes.

*No Windows.* `toolchains_llvm` does not produce a Windows toolchain (bazel-contrib/toolchains_llvm#4, open since the project began), even though the distribution set does list `clang+llvm-22.1.8-x86_64-pc-windows-msvc.tar.xz`. That is why Windows CI is scoped to `//modules/...`, and why C++/Java lint and format are Linux/macOS only: clang-tidy and clang-format come from this toolchain.

*No macOS Intel.* Upstream LLVM stopped publishing `x86_64-apple-darwin` after 15.0.7; at 22.1.8 the only darwin asset is `LLVM-22.1.8-macOS-ARM64.tar.xz`. Resolution fails outright with `No matching config could be found for version 22.1.8 on darwin/darwin/ with arch x86_64`, so the macOS Intel CI leg is disabled and macOS coverage is Apple Silicon only.

## Towards a solution

`tools/cpp/toolchains/remote_cc_toolchains.bzl` already names the candidate: the `llvm` BCR module (hermeticbuild/hermetic-llvm), whose "minimal" archive is a single static-musl multiplexed binary providing clang/lld/clang-tidy/clang-format and the llvm- binutils in **~41 MB**. We already download it for `--config=clang_remote`, linux-amd64 and linux-arm64 only. That is roughly a 50x reduction.

The comment there says the switch is "pending upstream `bazel coverage` support (hermeticbuild/hermetic-llvm#675)". **That issue was closed as completed on 2026-07-21**, and the BCR module has since reached **0.8.19**, so the stated blocker is gone and the comment is stale. Coverage is a CI gate here, so that is the first thing to verify.

### macOS Intel comes back for free

The published prebuilts ship `llvm-toolchain-minimal-23.1.0-darwin-amd64.tar.zst` (40.2 MB) alongside `darwin-arm64`, so hermetic-llvm carries the platform the official release dropped. The size swap and the macOS Intel gap are therefore the *same* piece of work — nothing extra is needed beyond re-enabling the runner.

### Windows is moving, but is not there yet

hermeticbuild/hermetic-llvm#726, "Add Windows MSVC LLVM prebuilts", **merged 2026-08-30**. It produces `windows-amd64-msvc` and `windows-arm64-msvc` archives built with clang-cl / llvm-ar / lld-link against static libc++ and `/MT`, verified to import only Windows system DLLs. That is the right shape for us.

Two caveats keep it off the table today:

1. The PR explicitly **does not publish** the archives, and lists as its own next steps "trigger and publish the LLVM prebuilt release containing both GNU and MSVC Windows assets" and "implement native Windows MSVC execution-toolchain support in a separate PR". A native Windows *execution* toolchain is precisely what our Windows runner needs, and it is not written yet. The latest prebuilt release, `llvm-23.1.0-1`, predates the merge, so no MSVC assets exist yet in any case.
2. That release's `llvm-toolchain-minimal-23.1.0-windows-{amd64,arm64}.tar.zst` are the **GNU/MinGW** variants. Our Windows leg is MSVC (`msvc-cl`, `/std:c++23preview`, `/MT` vs `/MD` CRT selection), so MinGW is not a drop-in.

Upstream tracking issues #24 (extended Windows support), #156 (native MSVC ABI targets), #722, #723 and #632 are all still open; none were closed by #726, though per #726's own description the MSVC *target* support landed in an earlier PR.

So the three strands do not resolve together: **size and macOS Intel are actionable now, Windows waits on the follow-up PR.**

## Steps

- confirm `bazel coverage --combined_report=lcov //...` produces a non-empty report under the `llvm` module at 0.8.19
- check clang-tidy and clang-format behave identically, since both gate CI
- swap `tools/cpp/llvm_segment.MODULE.bazel` and drop the two `toolchains_llvm` patches tracked in #9
- refresh the stale #675 comment in `remote_cc_toolchains.bzl` either way
- re-enable the macOS Intel leg in `.github/workflows/ci.yml` and drop the note above `build-macos`
- watch for the native Windows MSVC execution toolchain, then revisit the Windows scope in `.github/workflows/README.md`
