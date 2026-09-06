# PR draft — fix the MSVC pkg-config bootstrap on Windows ARM64

Repo: bazel-contrib/rules_foreign_cc
File: `foreign_cc/built_tools/pkgconfig_build.bzl`

---

## Title

fix(pkgconfig): build the MSVC bootstrap for the right arch on Windows ARM64

## Body

Building anything through `cmake()` or `make()` on a Windows ARM64 host fails
while bootstrapping the bundled pkg-config:

```
release\pkg-config\pkg.obj : fatal error LNK1112: module machine type 'ARM64'
  conflicts with target machine type 'x86'
NMAKE : fatal error U1077: 'link /machine:x86 ...' : return code '0x458'
```

### Cause

pkg-config's `detectenv-msvc.mak` infers the target architecture by
preprocessing a generated file that tests two CPU macros:

```
!if defined(_M_IX86)    → PLAT=Win32
!elif defined(_M_AMD64) → PLAT=x64
```

ARM64 `cl.exe` defines `_M_ARM64`, so neither branch is taken and `PLAT` is
never assigned. Two things follow from the empty value:

1. `LDFLAGS_ARCH` falls through to `/machine:x86` (`detectenv-msvc.mak:57-60`),
   which feeds `LDFLAGS_BASE` → `LDFLAGS` → the link line. ARM64 objects with
   an x86 target machine is the `LNK1112` above.
2. Every output path in `Makefile.vc` is `$(CFG)\$(PLAT)\...`, which collapses
   to `release\`. So `postfix_script` here, which copies from `release/x64/`,
   would not find the binary even if the link had succeeded.

pkg-config has had no release since 0.29.2 (2017), so the fix belongs on this
side rather than in the vendored sources.

### Fix

Add an ARM64-specific `config_setting` and, when it matches, pass `PLAT` and
`LDFLAGS_ARCH` to nmake as command-line macros — those take precedence over
the makefile's own assignments — and copy from the matching output directory.
x64 and non-Windows are untouched; they keep the existing autodetection.

### Notes on the select

`msvc_compiler_arm64` deliberately carries `@platforms//os:windows` in its
`constraint_values` even though the compiler flag already implies Windows. In
`postfix_script` it competes with the bare `@platforms//os:windows` key, and
without the shared constraint neither condition is a specialization of the
other, so `select()` reports an ambiguous match instead of picking the ARM64
branch.

### Testing

Verified the three-way resolution against a standalone platform matrix:

| `--platforms` | branch taken |
| --- | --- |
| windows + arm64 | new ARM64 branch |
| windows + x86_64 | existing Windows branch |
| linux (host) | default |

End to end, this takes a `windows-11-arm` GitHub runner from the `LNK1112`
above to a green build of a `cmake()` target (fmt), alongside an unchanged
Windows x64 leg.
