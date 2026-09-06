# Should the Python toolchain react to `--compilation_mode=dbg`?

This is the unaddressed half of #1823, and a question about what shape a fix should take before we write one.

## Already reported, not yet answered

#1823 has covered this since 2024-03-24. Its body names the missing capability directly:

> A similar issue occurs if the user defines `#Py_DEBUG`, which causes msvc to attempt linking against the debug binary python3xy_d.dll. **I did not see a way to request debug binaries using the python_repository rule** but if that were enabled, I think globbing `*.dll` would fix that case too.

A follow-up comment two days later states the failure exactly:

> Similarly, any `cc_library` depending on `@rules_python//python/cc:current_py_cc_headers` and including `<Python.h>` will also break when compiled with `-c dbg`, since this also causes `Python.h` to attempt to link to the `python3[xy]_d.lib`, which is not available.

The sibling case in that thread, the unversioned `python3.lib` needed for `Py_LIMITED_API`, was fixed by #1820 and merged 2024-11-30. The debug half was not, and the issue went stale in 2024-09.

## What happens today

`versions.bzl` hardcodes `build = INSTALL_ONLY`, and `install_only` is a release build, so every platform gets a release CPython regardless of compilation mode. `-c dbg` gives debug-compiled C++ against a release interpreter, and `sys.gettotalrefcount()` is unavailable everywhere.

On Unix that is mostly harmless: since 3.8 a debug build is ABI compatible with release, so nothing breaks, you simply do not get what you asked for. On Windows it is a link failure, for the reason quoted above. The usual workaround is to undefine `_DEBUG` across the include, which links but leaves a `/MDd` extension inside a `/MD` interpreter: two CRTs, two heaps.

## A debug interpreter removes the workaround

Measured on `windows-latest`, against a python-build-standalone distribution built with a `debug` option we patched in, then unpacked and linked with no workaround and only a `/LIBPATH`, so `pyconfig.h`'s own pragma had to resolve `python314_d.lib`:

```
build_options   : debug
Py_DEBUG        : 1
ABIFLAGS        : _d
EXT_SUFFIX      : _d.cp314-win_amd64.pyd

compiled with _DEBUG defined (debug CRT)
initialized: 3.14.7 (main, Aug 31 2026) [MSC v.1944 64 bit (AMD64)]
  refs added by 1000 objects : 1002
  refs still held after free : 2
  refs while a leak is held  : 1002
  refs after releasing it    : 2
  sub-interpreter : ok
  GIL save/restore: ok
PASS
```

It links, it runs, and it gives leak detection that a release interpreter cannot: `sys.gettotalrefcount` does not exist there.

## What a user can already do

On Linux and macOS, quite a lot, and we are not asking for something already possible. A debug interpreter can be dropped in today by registering a toolchain over the default, by pointing `local_runtime_repo` at a locally built debug CPython, or by `single_version_platform_override` against a `debug-full` archive. The 3.8 ABI guarantee means release wheels still import, so the swap is usable rather than a curiosity.

What none of those give is *conditionality*. Each replaces the interpreter for the whole build, so you get the debug one in every configuration rather than when `-c dbg` asks for it, and switching means editing `MODULE.bazel` rather than passing a flag. Selecting per configuration is the part that has to live in the toolchain machinery.

## Questions

1. **Is per-configuration selection of a debug interpreter something `rules_python` wants to own?** Unconditional swaps already work on Unix, so the question is specifically about making the choice a build flag rather than a module-file edit.

2. **If it is in scope, what should select it?** The free-threaded variants use an explicit flag (`//python/config_settings:py_freethreaded`) with `target_settings`, which looks like the established idiom. Reacting to `//command_line_option:compilation_mode` would match `rules_cc`, `rules_go` and `rules_rust`, and is what fixes #1823 without the user knowing any of this exists, but it makes toolchain resolution depend on the compilation mode, which may be unwelcome for analysis or caching reasons. We have no strong view and would rather follow yours.

3. **How should platforms without a debug distribution behave?** python-build-standalone publishes `debug-full` for 17 triples covering every Linux variant and both macOS architectures, and nothing for Windows (astral-sh/python-build-standalone#26, open since 2019). Windows is where the need is sharpest. Silent fallback keeps builds working but makes the flag quietly mean nothing; failing loudly is honest but breaks `-c dbg` on Windows outright.

## Scope worth stating up front

A debug interpreter does not imply debug-ABI extensions, and on Windows it cannot. There, `EXTENSION_SUFFIXES` is `['_d.cp314-win_amd64.pyd', '_d.pyd']`, so release wheels install but never load, while pip reports them as compatible. Across 1739 wheels in 20 major C-extension packages, none publish a `cp*d` tag. So on Windows the feature would deliver a debug interpreter for embedding, not a debug-ABI dependency graph, and it should not pretend otherwise.

## Offer

Happy to implement whichever shape you prefer. The mechanical part looks small: `_generate_platforms()` already multiplies platforms by free-threadedness through `target_settings`, and a debug dimension would follow the same pattern, with `strip_prefix = "python/install"` for the full archives and `sha256` entries only on the triples that have them.
