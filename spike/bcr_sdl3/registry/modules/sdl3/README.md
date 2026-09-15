# sdl3

SDL 3 built from source with rules_cc, as a static library. `overlay/BUILD.bazel`
documents the port; below is what a consumer and a version bump need.

## Targets

- `@sdl3` (`SDL3::SDL3-static`), `@sdl3//:sdl3_headers` (`SDL3::Headers`),
  `@sdl3//:sdl3_test` (`SDL3::SDL3_test`).
- Linux, macOS and Windows. On other platforms `@sdl3` is incompatible, so a
  wildcard build skips it.

## macOS: declare apple_support above rules_cc

The Objective-C sources are an `objc_library`, which needs the C++ toolchain
from `apple_support`. Bazel takes the first registered toolchain that matches,
and the root module registers first. A consumer whose `MODULE.bazel` declares
`rules_cc` before `apple_support`, or has no `apple_support` at all, gets the
autoconfigured toolchain and this error on macOS:

    Compiling objc_library targets requires the Apple CC toolchain

Declare `apple_support` above `rules_cc`, even with no Objective-C of your own:

```starlark
bazel_dep(name = "apple_support", version = "2.3.0")
bazel_dep(name = "rules_cc", version = "0.2.16")
bazel_dep(name = "sdl3", version = "3.4.16")
```

This is `apple_support`'s own requirement, and it applies to every module with
Objective-C sources.

## Build configuration

Windows and Apple platforms use the configs SDL ships in `include/build_config/`.
Linux gets the one SDL's CMake configure would generate: `sdl3_config_checks.bzl`
mirrors the probes in `CMakeLists.txt` and `cmake/sdlchecks.cmake` with
`rules_cc_autoconf`, and `autoconf_hdr` fills upstream's
`SDL_build_config.h.cmake`. Backends without a Bazel module are off: PulseAudio,
PipeWire, JACK, sndio, KMSDRM, libdecor, D-Bus (portal dialogs, IME, screensaver
inhibition), libudev (hotplug and the HIDAPI hidraw backend), libusb, liburing,
GLX (OpenGL goes through EGL, as on Wayland), fribidi, libthai. X11, Wayland,
ALSA and xkbcommon are loaded at runtime by soname. Their headers come from the
BCR modules in `MODULE.bazel`, at those versions or newer.

## Tests

`test/BUILD.bazel` runs every non-interactive program from `test/CMakeLists.txt`
the way ctest does: dummy video and audio drivers, `SDL_ASSERT=abort`,
`HAVE_BUILD_CONFIG`, and the no-SIMD reruns of testautomation and testplatform.
Where it differs from ctest:

- testprocess runs through `test/bazel_testprocess_main.cc`, which finds
  childprocess in the runfiles.
- `patches/0001-testprocess-bounded-EOF-search.patch` is upstream commit
  [32c19b9dc](https://github.com/libsdl-org/SDL/commit/32c19b9dc8c229e239434fedc94541c6abb3f84a).
  No 3.4.x release has it yet. Without it testprocess reads past a buffer and
  crashes on Windows ARM64, a platform SDL's own CI does not run tests on.
- testsem does not run on macOS, and testtimer is retried. Both assert on
  wall-clock durations, which GitHub-hosted macOS runners miss.
- ctest's `--trackmem` leak check is not reproduced; it is a regex over stdout.

## Upgrading

1. Diff `include/build_config/SDL_build_config.h.cmake` between the two
   releases. A new `#cmakedefine` needs a check in `sdl3_config_checks.bzl`, a
   removed one has a check to delete. A template entry with no check renders as
   `/* #undef NAME */` and a check with no entry is dropped, both silently:

   ```shell
   bazel build @sdl3//:config_h
   grep '#undef' "$(bazel cquery --output=files @sdl3//:config_h)"
   ```

   The expected `#undef` set is the Windows, Apple, console, BSD and
   optional-backend entries; anything else is a check to write.

2. Diff the `sdl_glob_sources`/`sdl_sources` calls in `CMakeLists.txt` against
   the source lists in `overlay/BUILD.bazel`; a new backend directory is a new
   glob. `wayland-protocols/*.xml` is globbed and needs nothing. testsymbols
   fails to link if a source file is missing.

3. If `test/testprocess.c` in the new release already bounds its EOF search
   (`SDL_strnstr`), delete `patches/` and the `patches` entry in `source.json`.

4. To confirm the Linux config against upstream, run SDL's own configure and
   compare `#define` lines with the generated header. On an Ubuntu with the
   X11, Wayland, xkbcommon, ALSA, GL and EGL dev packages installed:

   ```shell
   cmake -S SDL3-<version> -B build -DCMAKE_BUILD_TYPE=Release \
     -DSDL_SHARED=OFF -DSDL_STATIC=ON -DSDL_TESTS=OFF -DSDL_EXAMPLES=OFF \
     -DSDL_TEST_LIBRARY=OFF -DSDL_INSTALL=OFF \
     -DSDL_ALSA=ON -DSDL_PULSEAUDIO=OFF -DSDL_PIPEWIRE=OFF -DSDL_JACK=OFF \
     -DSDL_SNDIO=OFF -DSDL_OSS=OFF -DSDL_X11=ON -DSDL_X11_XSCRNSAVER=OFF \
     -DSDL_X11_XTEST=OFF -DSDL_FRIBIDI=OFF -DSDL_LIBTHAI=OFF -DSDL_WAYLAND=ON \
     -DSDL_WAYLAND_LIBDECOR=OFF -DSDL_KMSDRM=OFF -DSDL_OPENVR=OFF -DSDL_RPI=OFF \
     -DSDL_ROCKCHIP=OFF -DSDL_VIVANTE=OFF -DSDL_OPENGL=ON -DSDL_OPENGLES=ON \
     -DSDL_VULKAN=ON -DSDL_DBUS=OFF -DSDL_IBUS=OFF -DSDL_LIBUDEV=OFF \
     -DSDL_LIBURING=OFF -DSDL_HIDAPI_LIBUSB=OFF
   diff <(grep '^#define' build/include-config-release/build_config/SDL_build_config.h | sort) \
        <(grep '^#define' "$(bazel cquery --output=files @sdl3//:config_h)" | sort)
   ```

   Expected differences: `SDL_VIDEO_OPENGL_GLX` (CMake finds Mesa's
   `GL/glx.h`, the module has no GLX), the `SDL_DISABLE_<intrinsics>` lines
   (per CPU of the machine running CMake; the module leaves them to
   `SDL_intrin.h`), and the xkbcommon and libdecor version macros (the machine's
   packages against the module's floor).

5. `bazel run //tools:update_integrity -- sdl3 --version=<new>`, then the
   presubmit matrix. Windows ARM64 is in it because SDL's own MSVC build
   targets it and nothing here is x86-specific.
