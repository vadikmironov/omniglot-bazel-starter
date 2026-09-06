Windows ARM64 could not build any `cmake()` or `make()` target. Three of
rules_foreign_cc's tools have no ARM64 story:

| tool | problem |
| --- | --- |
| pkg-config | built against an external glib, and the only Windows glib binary ever published is the x64 build GNOME stopped shipping in 2010 |
| cmake | prebuilts mapped to `x86_64`/`i386` only, so it fell back to building CMake from source, which fails with `C1083` |
| ninja | prebuilts mapped to `x86_64` only |

This registers replacements from the root module, which outranks the toolchains
rules_foreign_cc registers for itself. The old bootstrap is not patched or
disabled — it is simply never selected, so glib is never fetched.

- **pkg-config** → pkgconf, built from source as a plain `cc_binary`. It has no
  dependencies, so it works wherever Bazel's C++ toolchain does.
- **cmake / ninja** → the official Kitware and ninja-build ARM64 binaries,
  constrained with `exec_compatible_with` so upstream prebuilts stay in charge
  everywhere else.

## Retires three carried patches

All three existed only to keep glib building, and nothing builds glib now:
`pkgconfig_gnu90` (upstream #1427), `msvc_pkgconfig_bzlmod_paths` (#1359), and
`pkgconfig_arm64_msvc`. rules_foreign_cc goes from five carried patches to two,
neither touching pkg-config. Issue #9 shrinks accordingly.

## Result

Green on Linux (Clang and GCC), macOS ARM64, Windows x64 and Windows ARM64.
The last of those is new — it now builds `//modules/...` including the
`cmake()` target. Dropping the CMake source build also removed 398 of the 401
warnings on that leg.

## Follow-up

Package pkgconf as a BCR module so rules_foreign_cc can consume it as a
`bazel_dep` and delete the bootstrap upstream rather than have it bypassed
here. The cmake and ninja platform gaps are a separate upstream fix — both
projects already publish the binaries, only the mapping is missing.

## Note on #193

This branch was cut from #193's and carries its commits, because `ci.yml` only
runs on PRs targeting `main` and ARM64 coverage needs the runner job it adds.
#193 cannot go green alone: its ARM64 leg fails on the glib bootstrap, which
its arm64 patch never addressed. This deletes that patch.
