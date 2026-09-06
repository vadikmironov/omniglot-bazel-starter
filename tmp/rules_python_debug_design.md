# rules_python debug interpreter: implementation options

Working notes to turn the open question into concrete proposals. Feeds `tmp/rules_python_debug_question.md`, which is still unpublished.

## The gap

`versions.bzl` hardcodes `build = INSTALL_ONLY` in `get_release_info`, and `install_only` is a release build. So `-c dbg` gets a release interpreter on every platform, and there is no flag that changes it.

## ABI: what actually breaks

This is the part that decides how much the feature can promise, and it is not symmetric.

**Unix is safe.** Since 3.8, ["the ABI of Python debug builds is now compatible with Python release builds"](https://docs.python.org/3/whatsnew/3.8.html#debug-build-uses-the-same-abi-as-release-build), and crucially the importer was widened: *"On Unix, when Python is built in debug mode, import now also looks for C extensions compiled in release mode and for C extensions compiled with the stable ABI."* A debug interpreter therefore loads the release wheels already in a lockfile. `Py_DEBUG` does not affect version resolution either, so `requirements_lock.txt` does not change.

**Windows is not.** Measured on a debug CPython 3.14.7:

```
EXTENSION_SUFFIXES: ['_d.cp314-win_amd64.pyd', '_d.pyd']
```

Only `_d` variants. A release wheel's `_speedups.cp314-win_amd64.pyd` is on disk and invisible to the importer. Worse, pip disagrees with the importer:

```
Compatible tags: cp314-cp314d-win_amd64, cp314-cp314-win_amd64, cp314-abi3-win_amd64, ...
Successfully installed markupsafe-3.0.3 pyyaml-6.0.3
```

pip installs release wheels happily, then `import markupsafe._speedups` raises `ModuleNotFoundError`. Packages with a pure-Python fallback degrade silently to the slow path; packages without one fail hard. Across 1739 wheels in 20 major C-extension packages, **zero** publish a `cp*d` ABI tag, while free-threaded `cp313t`/`cp314t` tags are common: the debug ABI is absent by convention, not blocked by tooling.

So any design has to treat "debug interpreter" and "debug-ABI extensions" as separate concerns, and must not imply the second on Windows.

**Free-threaded Windows adds a second, version-dependent hazard.** MSVC embedders
normally never name an import library: `pyconfig.h` picks one through
`#pragma comment(lib, ...)`, keyed on `_DEBUG` and `Py_GIL_DISABLED`. Which side
declares the latter changed in 3.14:

| version | installed `pyconfig.h` | who declares free-threading |
| --- | --- | --- |
| ≤ 3.13 | generated per configuration from `PC/pyconfig.h.in` | the header — a free-threaded install defines `Py_GIL_DISABLED` itself |
| ≥ 3.14 | static `PC/pyconfig.h`, shipped verbatim | the consumer — the header only normalises an externally supplied `0` to undefined |

The 3.14 header states the intent: *"every effort should be made to avoid
defining the variable at all when not desired. However,
`sysconfig.get_config_var` always returns a 1 or a 0, and so it seems likely
that a build backend will define it with the value."*

So from 3.14 a free-threaded install no longer self-identifies. An embedder that
does not pass `/DPy_GIL_DISABLED=1` gets a pragma naming `python314_d.lib`,
which a free-threaded distribution correctly does not ship, and the link fails
with `LNK1104`. The value must come from
`sysconfig.get_config_var("Py_GIL_DISABLED")`, not from the version number.

This is a real constraint on any toolchain that hands out a free-threaded
Windows interpreter, debug or not, and it applies equally to release builds —
the `_d` suffix only changes which name is wrong.

## Availability

PBS publishes `debug-full` for **17** triples covering every Linux variant and both macOS architectures. It publishes **none** for Windows (astral-sh/python-build-standalone#26, open since 2019).

Size is not the objection it looks like. For `x86_64-unknown-linux-gnu` 3.14.7:

| archive | size |
| --- | --- |
| `debug-full.tar.zst` | 41 MB |
| `install_only.tar.gz` | 120 MB |
| `install_only_stripped.tar.gz` | 34 MB |

The debug archive downloads smaller than the release archive rules_python uses today, because it is zstd and carries no PGO/LTO. It is a *full* archive, so it unpacks a `build/` tree as well, and needs `strip_prefix = "python/install"` rather than the `python` default.

## Options

**A. Explicit flag, mirroring free-threading.** A `//python/config_settings:py_debug` flag with `yes`/`no`, selecting the archive through `target_settings` exactly as `_is_py_freethreaded_yes/_no` does.

- follows the established idiom, so it is the most likely to be accepted
- no dependency on `--compilation_mode` in toolchain resolution
- does not fix the Windows `-c dbg` link failure by itself: the user has to know to pass both flags

**B. React to `--compilation_mode`.** Toolchain resolution keys off `//command_line_option:compilation_mode`, so `-c dbg` selects the debug interpreter.

- matches `rules_cc`, `rules_go` and `rules_rust`, and is what a Bazel user expects
- fixes the embedding link failure without the user knowing any of this exists
- novel for this ruleset, and makes the interpreter change under a build-wide flag, so every `-c dbg` build refetches an interpreter and rebuilds every Python target
- risks surprising users who wanted debug C++ and not a different interpreter

**C. Flag with three values: `no` (default), `yes`, `auto`.** `auto` follows `compilation_mode`.

- default behaviour unchanged, so nothing surprises anyone
- opt-in to the automatic binding for projects that embed CPython
- costs a three-state flag instead of a boolean

## Fallback where no debug archive exists

Windows today, and any platform PBS has not built.

- **explicit `yes`**: fail at toolchain resolution. The user asked for something unavailable and a silent release interpreter would be a lie.
- **`auto` / compilation-mode-driven**: fall back to release silently. That is exactly today's behaviour, so it is not a regression, and erroring would break `-c dbg` on Windows outright.

## Recommendation

Stage it as two changes, so the uncontroversial half is not held up by the debatable half.

1. **Option A first.** Adds the capability, follows the freethreaded precedent, unblocks Linux and macOS immediately. Small and self-contained.
2. **Option C second**, as an `auto` value on the same flag. Argue it on the Windows embedding case, where the compilation mode and the interpreter genuinely have to agree, and let the maintainers decide whether toolchain resolution may depend on `compilation_mode`.

If only the first lands, we can still bind it ourselves with `single_version_platform_override` and a local config setting.

## Implementation sketch

- `versions.bzl`: add `DEBUG = "debug-full"` beside `INSTALL_ONLY`, and thread the variant into `get_release_info` rather than hardcoding `build`
- `_generate_platforms()`: currently multiplies platforms by freethreadedness; becomes a 2x2 with debug, so platform keys grow a `-debug` suffix as they grow `-freethreaded`
- the variant has to carry `strip_prefix`, since full archives need `python/install` and `install_only` needs `python`
- `TOOL_VERSIONS` needs `sha256` entries for the debug archives, on the 17 triples that have them and no others
- `python.single_version_platform_override` already accepts `urls`, `sha256`, `strip_prefix` and `target_settings`, so this is expressible in a user repo first as a working demonstration to attach to the request

## Open questions for maintainers

1. Is per-configuration interpreter selection something rules_python wants to own, given unconditional swaps already work on Unix via toolchain registration or `local_runtime_repo`?
2. Is a dependency on `//command_line_option:compilation_mode` acceptable in toolchain resolution, or is an explicit flag the only shape they will take?
3. Should the flag be rejected, or silently ignored, on platforms with no debug distribution?
