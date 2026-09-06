# Draft: PBS PR for issue #26 (Windows debug builds)

**Write the PR body yourself.** astral's AI policy asks that the body and any
replies be in your own words. Everything below is raw material -- facts,
evidence and structure -- not prose to paste.

Target issue: https://github.com/astral-sh/python-build-standalone/issues/26
("Add debug support for MSVC builds", open since 2019-11-27, one comment)

---

## Suggested title

Add a debug build option for Windows

## Commit split

Three commits, in this order. The first two have to land together: the first
produces artifacts the second is needed to accept, so CI fails on either alone.
The third is what makes any of it get built.

**1. Add a debug build option for Windows** (patch 0003, `cpython-windows/build.py`)

- `debug` joins the `--options` set beside `noopt` and `pgo`, matching the
  spelling `cpython-unix/build.py` already uses, so `debug+pgo` is simply not a
  valid combination
- the set is renamed `optimizations` -> `options`, since debug is not one
- `configuration="Debug"` reaches msbuild, and `artifact_config` follows
- `PC/layout` is passed `--debug`, which is what makes it expect `_d` artifacts
- executables, extension libraries and dependency libraries pick up the `_d`
  suffix that `$(PyDebugExt)` produces
- the tail-calling interpreter is not enabled for Debug

**2. Accept a Windows debug distribution in the validator** (patch 0004, `src/validation.rs`)

- the PE allow list gains the debug CRT (`ucrtbased.dll`, `VCRUNTIME140D.dll`,
  `VCRUNTIME140_1D.dll`), the `_d` interpreter DLLs and `sqlite3_d.dll`
- each debug name sits beside its release counterpart, as the Mach-O list
  already does for `libpython3.14d.dylib`
- the `abiflags` check consults `EXT_SUFFIX` on Windows

**3. Build the Windows debug configurations in CI** (patch 0005, `ci-targets.yaml`)

- each Windows target has `pgo` and `freethreaded+pgo` today, so each gains the
  matching `debug` and `freethreaded+debug`
- that is six configurations, and it leaves the three targets in step with each
  other as they already were
- Unix targets have carried `debug` and `freethreaded+debug` all along, so this
  is parity rather than a new idea

## Evidence

Every configuration patch 0005 adds was built and validated — 26 in all, each
on its own architecture rather than cross-compiled, and all green:

| options | versions | architectures |
| --- | --- | --- |
| `debug` | 3.10–3.15 | x64, x86, and arm64 from 3.11 |
| `freethreaded+debug` | 3.13–3.15 | x64, x86, arm64 |

Each distribution passes `validate-distribution`, and was then unpacked and
checked: `build_options` carrying `debug`, `EXT_SUFFIX` carrying `_d`, and the
`_d` artifacts present under the right name — `python314_d` for a plain debug
build, `python314t_d` for a free-threaded one.

An embedder was then compiled `/MDd` against each with no `_DEBUG` workaround
and only a `/LIBPATH`, so `pyconfig.h`'s own `#pragma comment(lib, ...)` had to
resolve the import library by itself. Free-threaded builds additionally pass
`/DPy_GIL_DISABLED=1`, taken from `PYTHON.json`'s config vars, for the reason in
the third finding below. It links, and at runtime `sys.gettotalrefcount()`
tracks allocation and release, which a release interpreter cannot do at all.

## Three findings worth mentioning in the PR

**The tail-calling interpreter cannot be used in a Debug build.** `build.py`
enables `UseTailCallInterp` for 3.15 on x64. A guaranteed tail call needs
optimisations that `/Od` removes, so MSVC reports C4737 at every dispatch site
until the count trips C1003. This is not a bug in either feature; the
combination was simply unreachable before.

**`Py_DEBUG` and `ABIFLAGS` only reach Windows config vars from 3.14.**
`sysconfig._init_non_posix` gained them with `_sysconfig.config_vars()`, and
CPython deliberately keeps the lowercase `abiflags` empty on Windows because it
feeds path construction. `EXT_SUFFIX` carries the `_d` marker in every
supported version, so the validator uses that.

**From 3.14 a free-threaded Windows install no longer declares itself.** Up to
3.13 the installed `pyconfig.h` was generated per configuration from
`PC/pyconfig.h.in`, and a free-threaded build defined `Py_GIL_DISABLED` in it.
3.14 ships a static `PC/pyconfig.h` that only normalises an externally supplied
value, so an MSVC embedder that does not pass `/DPy_GIL_DISABLED=1` gets a
`#pragma comment(lib, ...)` naming `python314_d.lib` and fails to link against a
free-threaded distribution. The value has to come from
`sysconfig.get_config_var("Py_GIL_DISABLED")`, which PBS already records in
`PYTHON.json`. Nothing in this PR changes because of it — the distributions are
correct — but it is worth stating, since it applies to existing free-threaded
release builds too.

## Known limitations to state plainly

- `debug` is not combined with `pgo`, by construction
- 3.10 has no arm64 configuration, following what `ci-targets.yaml` already
  lists for that version rather than adding one
- the tail-calling interpreter is disabled under Debug, per the first finding
- release-ABI wheels install into a debug interpreter but never load, because
  Windows extension suffixes are `_d`-prefixed. That is CPython behaviour, not
  something this changes, but it bounds what a debug distribution is useful for

## Not in this PR

Publishing the archives, and the release workflow that would carry them. This
adds the option and builds it; whether a debug distribution is published is a
separate decision.

Which runner the aarch64 targets use. `add_python_build_entries_for_config`
asks `find_runner` for a non-free runner, which is what `free: false` on
`windows-11-arm` selects, so those builds already run on an arm64 host and
`PC/layout` can execute the interpreter it just built. Whether that runner is
still the right choice is a cost question, and a separate one.
