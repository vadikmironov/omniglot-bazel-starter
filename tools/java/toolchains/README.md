# Java Toolchains

This directory contains custom Amazon Corretto JDK toolchain configurations that complement [rules_java](https://github.com/bazelbuild/rules_java). While rules_java provides built-in support for Azul Zulu JDKs, these configurations demonstrate how to use alternative JDK distributions with both remote (auto-downloaded) and local (pre-installed) toolchains.

Toolchain selection flags:
- `--java_runtime_version` — selects which JDK runs your code
- `--tool_java_runtime_version` — selects which JDK runs build tools
- `--java_language_version` — sets the Java language level for compilation

## What's in This Directory

| File | Description |
|------|-------------|
| `remote_corretto_toolchains.bzl` | Module extension providing Amazon Corretto JDKs that are downloaded on-demand during builds |
| `local_corretto_toolchains.bzl` | Module extension for pre-installed local Corretto JDKs |
| `local_corretto_toolchains_setup.sh` | Helper script to download and install Corretto JDKs locally |

## Supported Configurations

**JDK Versions**: 8, 11, 17, 21, 25

**Platforms** (remote toolchains):
- Linux: x86_64, aarch64
- macOS: x86_64, aarch64 (Apple Silicon)
- Windows: x86_64

## Quick Start

### Using Remote Corretto Toolchains (Recommended)

Remote toolchains require no setup—JDKs are downloaded automatically when needed:

```bash
bazel build --config=java_17_remote_corretto_jdk //your:target
```

### Using Local Corretto Toolchains

1. Run the setup script to download JDKs to `/opt/corretto_jdks`:
   ```bash
   ./local_corretto_toolchains_setup.sh --toolchain_root_path /opt/corretto_jdks
   ```

2. Build with the local toolchain:
   ```bash
   bazel build --config=java_17_local_corretto_jdk //your:target
   ```

## Integration Details

These toolchains are integrated via Bazel's module extension system in `java_segment.MODULE.bazel`. The integration includes:

- **Remote toolchains**: Use on-demand registration via `--extra_toolchains` in `.bazelrc`
- **Local toolchains**: Globally registered via `register_toolchains()` in MODULE.bazel

For detailed integration documentation, including how `remote_java_repository` and `local_java_repository` work, see the extensive comments in [`java_segment.MODULE.bazel`](../java_segment.MODULE.bazel).

## Available .bazelrc Configurations

```bash
# Local Corretto JDK 17
--config=java_17_local_corretto_jdk

# Remote Corretto JDK 17 (auto-downloaded)
--config=java_17_remote_corretto_jdk

# Debug toolchain resolution
--config=java_17_local_corretto_jdk_debug
```

## Updating JDK Versions

To update to newer Corretto releases:

1. **Remote toolchains**: Update URLs, checksums, and version strings in `remote_corretto_toolchains.bzl`. Release information is available at:
   - [Corretto 8](https://github.com/corretto/corretto-8/releases)
   - [Corretto 11](https://github.com/corretto/corretto-11/releases)
   - [Corretto 17](https://github.com/corretto/corretto-17/releases)
   - [Corretto 21](https://github.com/corretto/corretto-21/releases)
   - [Corretto 25](https://github.com/corretto/corretto-25/releases)

2. **Local toolchains**: Re-run `local_corretto_toolchains_setup.sh`—it always fetches the latest versions.
