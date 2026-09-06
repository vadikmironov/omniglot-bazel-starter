# Scope: replace the glib/pkg-config MSVC bootstrap with pkgconf

Repo: bazel-contrib/rules_foreign_cc (0.15.1 is current; main is ~99 commits ahead)

## The problem

`cmake()` and `make()` unconditionally require `pkgconfig_toolchain`
(`foreign_cc/cmake.bzl:436`, `meson.bzl:254`). On MSVC that toolchain is built
from pkg-config 0.29.x via `Makefile.vc`, which links against an **external**
glib supplied by `toolchains/built_toolchains.bzl:270`:

```
https://download.gnome.org/binaries/win64/glib/2.26/glib-dev_2.26.1-1_win64.zip
```

Three things are wrong with that archive:

1. It is **win64 only**. There is no ARM64 build, so every `cmake()`/`make()`
   target fails on Windows ARM64 at link time with ~60 `LNK2001: unresolved
   external symbol g_*`.
2. It is from **2010**. GNOME stopped publishing Windows binaries shortly
   after; this is the last artifact of a dead distribution channel, not a
   considered pin.
3. It is **older than the glib pkg-config already ships**. The pkg-config
   tarball bundles glib 2.38 under `glib/`, and the Unix path in
   `foreign_cc/built_tools/pkgconfig_build.bzl:72` already uses
   `--with-internal-glib` and needs no external glib at all. Only the MSVC path
   reaches outside, because `Makefile.vc` has no internal-glib mode — it
   hardcodes `GLIB_PREFIX = ..\vs$(VSVER)\$(PLAT)`.

The glib bootstrap is also a recurring source of breakage unrelated to ARM64:

| issue | |
| --- | --- |
| #1200 (open) | pkg-config build broken on clang 15+ and gcc 14+ |
| #1427 (open) | glib `goption.c` fails under GCC 15's C23 default |
| #1198 (open) | `@glib_dev` cannot be resolved |
| #1191 (open) | `gettext_runtime` unknown repo |
| #1359 (closed) | `pkgconfig_tool_msvc_build_` fails on Windows |

Every one of these is the glib dependency, not pkg-config itself.

## Why pkgconf

[pkgconf](https://github.com/pkgconf/pkgconf) is the maintained replacement,
shipped as `/usr/bin/pkg-config` by Fedora, Arch, Alpine and FreeBSD.

- **No glib dependency, no external dependencies at all.**
- Actively maintained: 3.0.6 on 2026-08-23, four releases in the two months
  before that.
- Small: 22 `.c` files in `libpkgconf`, 4 in `cli`.
- Its feature detection is modest — 10 `HAVE_*` function probes, 6 feature-test
  macros, and a handful of quoted path defaults (`SYSTEM_LIBDIR`,
  `SYSTEM_INCLUDEDIR`, `PKG_DEFAULT_PATH`, `PERSONALITY_PATH`).

Not in BCR (checked `bcr.bazel.build/modules/{pkgconf,pkgconf.bzl,rules_pkgconf}`
— all 404).

## Packaging: a BCR module, not vendored sources

The build work below is the same wherever it lives, but the packaging decision
is separate and matters more.

Publishing pkgconf as its own Bazel module and having rules_foreign_cc consume
it as a `bazel_dep` is the better shape:

- It reduces the rules_foreign_cc change to deleting a bootstrap and adding one
  dependency. That is a far easier ask of a repo whose last release was 14
  months ago than a new vendored build.
- It is reusable by anyone, not just rules_foreign_cc.
- It matches where the ecosystem is already going — `jq.bzl`, `yq.bzl` and
  `tar.bzl` are exactly this pattern, the modules bazel-lib v3 decomposed into.
- No cycle: pkgconf builds with plain `cc_binary` against `rules_cc`, so a
  module has no path back to rules_foreign_cc.
- Exec-platform correctness falls out. The tool is needed on the exec platform,
  and `cc_binary` in the exec configuration gives that natively — better than
  today's prebuilt archive, which is fixed at win64 regardless of exec arch.

Upstream artifacts that make this straightforward:

- Source tarballs per release (`pkgconf-3.0.6.tar.gz`, 610 KB) for `http_archive`.
- Official Windows **arm64**, x64 and x86 MSIs, confirming ARM64 is a supported
  upstream configuration. MSI is awkward to unpack in Bazel, so source build is
  still preferred, but it settles the platform question.

No Bazel packaging of pkgconf exists today, and pkgconf's tracker has no Bazel
mentions, so this is greenfield.

### Where the Bazel files live

| | approach | needs pkgconf maintainers? |
| --- | --- | --- |
| upstream | add `MODULE.bazel` + `BUILD` to pkgconf/pkgconf | yes — cold ask, no Bazel history there |
| separate module | a `pkgconf.bzl`-style repo that `http_archive`s the release and applies a BUILD | no |

The separate-module route is the established bazel-contrib pattern and does not
depend on pkgconf accepting Bazel files. The cost either way is an ongoing
maintenance obligation once it is in BCR.

## Options

### A. Build it with Bazel's own `cc_binary` — recommended

Ship a `build_file_content` for a `pkgconf_src` archive that compiles the 26 C
files with `cc_binary`, plus a checked-in `config.h` per platform family.

- Removes the bootstrap entirely: no meson, no ninja, no nmake, no
  `Makefile.vc`, no shell fragments.
- Works on every platform Bazel's C++ toolchain supports, so ARM64 needs no
  special case.
- Sidesteps the circularity below by construction.
- Cost: the hand-written `config.h`. On MSVC all 10 probes have known constant
  answers; on Unix the same, keyed off the existing platform selects.

### B. Build it with meson

pkgconf's only real build system is meson. `Makefile.lite` explicitly
"does not include cross-compile support and MSVC support", and `cmake/` holds
only consumer-facing config templates.

- **Circularity:** `meson()` requires `pkgconfig_toolchain`, so the public rule
  cannot build the pkg-config tool. It would need a bootstrap variant that
  declares its own toolchains, the pattern `pkgconfig_tool_unix` and
  `make_variant` already use.
- meson itself is fine — `meson_tool` is a plain `py_binary` over `meson_src`,
  so it is arch-independent.
- Adds ninja to the bootstrap chain on Windows, or a `--backend=vs` path.
- More moving parts than A for no extra capability, since pkgconf has no
  dependencies for meson to discover.

### C. Keep pkg-config, get an ARM64 glib

- `mingw-w64-clang-aarch64-glib2` exists in MSYS2, but ships `.dll.a` import
  libraries that MSVC's `link.exe` cannot consume. Would need a `.lib`
  generated from the DLL, or moving the bootstrap to clang-aarch64.
- Building glib from source pulls in meson, pcre2, libffi and gettext.
- Leaves #1200/#1427/#1198/#1191 all in place.

## Risks

**Bug compatibility.** pkgconf's README is explicit: *"does not provide
bug-compatibility with the original pkg-config"*, with a section saying so
again. In practice most distros already ship it as `pkg-config`, so exposure is
low — but it is a behaviour change, not a pure substitution, and it is the one
thing that could surprise a downstream consumer.

**Interface.** Low risk: `native_tool_toolchain` sets `PKG_CONFIG` to the tool
path via `$(execpath)`, so the binary's name is not load-bearing.

**Scope of the change.** Replacing the Unix path as well as MSVC is a larger
blast radius than fixing ARM64. A first PR could convert only the MSVC path and
leave `--with-internal-glib` alone, at the cost of carrying two implementations.

## What it retires

- `glib_dev`, `glib_src`, `gettext_runtime` repos and the `Makefile.vc` shell
  fragments.
- Our `rules_foreign_cc_0.15.1_pkgconfig_gnu90.patch` (#1427).
- Our `rules_foreign_cc_0.15.1_pkgconfig_arm64_msvc.patch`, which only exists to
  fix arch detection in `detectenv-msvc.mak`.
- Plausibly #1200, #1198, #1191.

## Immediate unblock

Independent of the above: tag `//modules/cpp_app_with_cmake_dep` and add it to
`exclude_tags` for the `windows-arm64` matrix entry, so PR #193 goes green
without waiting on upstream. Record in `.github/workflows/README.md` that
Windows ARM64 excludes foreign-cc targets, and why.

## Next step

Sequenced, because the module has to exist before rules_foreign_cc can consume
it:

1. Build the `cc_binary` + `config.h` against a pinned pkgconf release and prove
   it on Linux, macOS, Windows x64 and Windows ARM64. This is the real work and
   is identical regardless of packaging, so it can start before the packaging
   question is settled.
2. Package it as a module and publish to BCR.
3. PR rules_foreign_cc: delete `glib_dev`, `glib_src`, `gettext_runtime` and the
   `Makefile.vc` fragments, add the `bazel_dep`, keep the
   `native_tool_toolchain` interface unchanged so consumers see no difference.

rules_foreign_cc's tracker returns zero results for "pkgconf", so step 3 is a
cold proposal. Worth asking there — with step 1 already working as evidence —
whether they want the Unix path converted in the same series or left on
`--with-internal-glib` initially.
