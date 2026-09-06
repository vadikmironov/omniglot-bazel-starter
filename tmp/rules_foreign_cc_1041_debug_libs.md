# rules_foreign_cc: CMake debug postfixes break `out_static_libs`

Target issue: **https://github.com/bazel-contrib/rules_foreign_cc/issues/1041** ("cmake debug build failed", open since 2023-04-12)

Related, closed without a fix: https://github.com/bazel-contrib/rules_foreign_cc/issues/792 ("`cache_entries` argument ignore empty variable")

## Status

Draft. The diagnosis half is reportable now. The proposal half needs an implementation behind it before it goes upstream.

## The symptom

`-c dbg` sets `CMAKE_BUILD_TYPE=Debug`, projects append their debug postfix, and the declared output no longer matches what CMake produced:

```
WARNING: Remote Cache: Expected output .../fmt/lib/libfmt.a was not created locally.
ERROR: output 'modules/cpp_app_with_cmake_dep/fmt/lib/libfmt.a' was not created
ERROR: Foreign Cc - CMake: Building fmt failed: not all outputs were created or valid
```

Reproduced locally against `fmt`. The install directory contained exactly one file, `libfmtd.a`. Analysis is unaffected; this is an execution-time failure, so nothing is silently mislinked.

#1041 reports the same against thrift, and a second reporter against spdlog in 2024.

## Why the documented workaround does not work

rules_foreign_cc creates the condition itself, in `foreign_cc/private/cmake_script.bzl`:

```python
build_type = params.cache.get(
    "CMAKE_BUILD_TYPE",
    "Debug" if is_debug_mode else "Release",
)
```

The natural fix is to pin the postfix off, which is what #792 asked for:

```python
cache_entries = {"FMT_DEBUG_POSTFIX": ""}
```

That cannot work, because `""` is overloaded to mean *omit this variable*:

```python
# Give user the ability to suppress some value, taken from Bazel's toolchain,
# or to suppress calculated CMAKE_BUILD_TYPE
# If the user passes "CMAKE_BUILD_TYPE": "" (empty string),
# CMAKE_BUILD_TYPE will not be passed to CMake
_wipe_empty_values(params.cache, keys_with_empty_values_in_user_cache)
```

So "do not pass this variable" and "pass this variable as the empty string" share one spelling, and only the first is reachable. Suppressing a debug postfix requires the second. #1041's second reporter confirms `-DCMAKE_DEBUG_POSTFIX=""` does not help.

#792 was closed by the stale bot in 2022, not by a fix.

## Why this is not a Bazel limitation

Bazel requires outputs declared at analysis time, and `CcInfo` needs concrete `File` objects because a linker cannot take a directory. Both are real. Neither requires the declared name to equal CMake's name.

Bazel's contract is *guarantee this file exists when the action finishes*, not *predict what the tool will call it*. rules_foreign_cc already runs a generated wrapper script and already copies the whole install tree:

```python
installdir_copy = copy_directory(ctx.actions, "$$INSTALLDIR$$", "copy_{}/{}".format(lib_name, lib_name))
```

It also already uses the escape hatch for genuinely unpredictable outputs; headers are a tree artifact:

```python
out_include_dir = ctx.actions.declare_directory(lib_name + "/" + attrs.out_include_dir)
```

Libraries take the other path, which is right for consumption and wrong for naming.

## Proposal

Reshape execution output to the declared contract instead of predicting it.

1. **Diagnostics first, independent of everything else.** When a declared library is missing, list what is actually in `out_lib_dir` before failing. The directory is already copied and sitting there. This turns a guessing game into a one-glance fix and changes no behaviour.

2. **Normalise names in the wrapper script.** Declare the stable name, then reconcile after `cmake --install`. CMake publishes what it produced, and rules_foreign_cc reads none of it today:
   - `install_manifest.txt`, written by `cmake --install`, lists every installed file
   - the [CMake File API](https://cmake.org/cmake/help/latest/manual/cmake-file-api.7.html) `codemodel-v2` object lists targets with their `artifacts`

   For a single-library project a glob suffices; the manifest is what disambiguates multi-library projects.

3. **Give omission its own spelling**, so `""` can mean the empty string. Fixes #792 and makes the postfix pinnable by hand. Smaller than (2) and independent of it, though (2) makes it unnecessary for this particular symptom.

## Notes

- (1) is small, obviously correct, and useful even if (2) is rejected, so it is the natural first PR.
- (2) is the change that makes `out_static_libs` mean what users assume. It is also the one that needs prototyping before being proposed.
- Our own tree carries the workaround this would remove, in `modules/cpp_app_with_cmake_dep/BUILD`: a four-way `select` over os x compilation_mode, because the name varies on both axes at once.
