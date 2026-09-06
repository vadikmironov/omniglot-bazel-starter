# Draft: jq.bzl PR for Windows arm64

**Write the body yourself.** Raw material below.

Patch: `tmp/jqbzl_windows_arm64.patch` (applies to v0.6.1)

## Suggested title

Add jq 1.8.2 and a windows_arm64 platform

## The problem

On a Windows arm64 host, toolchain resolution fails:

```
ERROR: While resolving toolchains for target @@..._jq_toolchains//:...
```

`JQ_PLATFORMS` lists `darwin_amd64`, `darwin_arm64`, `linux_amd64`,
`linux_arm64`, `linux_riscv64` and `windows_amd64`. There is no Windows arm64
entry, and `DEFAULT_JQ_VERSION` is `1.7`.

## Why it can be fixed now

jq itself publishes the binary. `jq-windows-arm64.exe` first appears in 1.8.0
and is present in 1.8.2, tracked by jqlang/jq#3340, closed as completed in
July 2025. Nothing was waiting on jq.

## The change

- `jq/toolchain/versions.bzl`: add the 1.8.2 hashes, including `windows-arm64`
- `jq/toolchain/platforms.bzl`: add `windows_arm64`, release platform
  `windows-arm64`
- `jq/toolchain/toolchain.bzl`: `DEFAULT_JQ_VERSION` to 1.8.2

The default has to move, because `extensions.bzl` creates a repository for
every entry in `JQ_PLATFORMS` at `DEFAULT_JQ_VERSION`, and 1.7 has no arm64
asset to point at.

## Worth stating

Someone pinning `version = "1.7"` on Windows arm64 will still fail, and the
error will be a missing dictionary key rather than a clear message. That is
accurate -- the binary does not exist for 1.7 -- but a nicer error might be
worth a follow-up.

## Verification

Integrity values were computed from the released binaries with the recipe in
the file header, and cross-checked against the `sha256sum.txt` jq publishes
with each release.
