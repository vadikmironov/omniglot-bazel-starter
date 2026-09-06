# Draft: PBS issue — free-threaded Windows installs and Py_GIL_DISABLED

**Write the issue yourself.** astral's AI policy asks that the text and any
follow-up replies be in your own words. This is raw material, not a body to
paste.

Repo: astral-sh/python-build-standalone

Note this is a question rather than a bug report — the distributions are
correct and nothing here asks for a code change up front. If they want the
disttests suggestion, that is a PR we can write.

## Suggested title

Free-threaded Windows distributions: should anything surface the
`Py_GIL_DISABLED` requirement for embedders?

## The behaviour

On Windows, MSVC consumers normally never name a Python import library.
`pyconfig.h` picks one through `#pragma comment(lib, ...)`, keyed on `_DEBUG`
and `Py_GIL_DISABLED`. Which side declares the second changed in 3.14:

| version | installed `pyconfig.h` | declares free-threading |
| --- | --- | --- |
| ≤ 3.13 | generated per configuration from `PC/pyconfig.h.in` | the header — a free-threaded install defines `Py_GIL_DISABLED` itself |
| ≥ 3.14 | static `PC/pyconfig.h`, shipped verbatim | the consumer — the header only normalises an externally supplied `0` to undefined |

The 3.14 header states the intent directly:

> every effort should be made to avoid defining the variable at all when not
> desired. However, `sysconfig.get_config_var` always returns a 1 or a 0, and
> so it seems likely that a build backend will define it with the value.

So from 3.14 an embedder that does not pass `/DPy_GIL_DISABLED=1` gets a pragma
naming `python314.lib`, which a free-threaded distribution correctly does not
ship, and the link fails with `LNK1104`.

## Why it is worth raising here

The distributions are right — `python314t.dll`, `libs/python314t.lib` and an
`EXT_SUFFIX` of `.cp314t-win_amd64.pyd` are all present and consistent, and
`PYTHON.json` already records `Py_GIL_DISABLED` under `python_config_vars`
because `generate_metadata.py` dumps all of `sysconfig.get_config_vars()`. Every
piece a consumer needs is published.

What is missing is any signal that the consumer has to use it. The failure
surfaces as a linker error naming a library that legitimately does not exist,
which points the reader at the distribution rather than at their own missing
define. It applies to the existing free-threaded release builds for 3.14 and
3.15, not only to debug ones — the `_d` suffix only changes which name is wrong.

## Possible responses

1. Nothing. It is CPython's contract, and consumers should read `sysconfig`.
2. A line in the docs for free-threaded Windows distributions.
3. Extend the disttests. `pythonbuild/disttests` already asserts
   `sysconfig.get_config_var("Py_GIL_DISABLED")` matches `BUILD_OPTIONS`; a test
   that compiles and links a small embedder would catch the whole chain, and
   would have caught this.

Option 3 is the one we would offer a PR for if it is wanted.

## How it was found

Building debug distributions for every supported Windows version and
architecture. The free-threaded 3.14 and 3.15 targets built correctly but an
embedder probe failed to link against them, while 3.13 linked. The difference
was the header, not the build.
