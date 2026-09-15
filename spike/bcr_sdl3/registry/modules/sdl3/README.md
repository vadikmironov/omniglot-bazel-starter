# sdl3

SDL 3 built from source with rules_cc, as a static library. `overlay/BUILD.bazel`
documents the port; below is what a consumer and a version bump need.

## Targets

- `@sdl3` (`SDL3::SDL3-static`), `@sdl3//:sdl3_headers` (`SDL3::Headers`),
  `@sdl3//:sdl3_test` (`SDL3::SDL3_test`).
- Linux, macOS and Windows. On other platforms `@sdl3` is incompatible, so a
  wildcard build skips it.

## macOS

SDL's Objective-C sources compile through `cc_library`, as Objective-C with ARC,
so any C toolchain that targets macOS builds them: `apple_support`'s, the one
`rules_cc` configures, or `toolchains_llvm`'s. A consumer needs no
`apple_support` dependency and no particular `bazel_dep` order. `objc_library`
would work only with `apple_support`'s toolchain registered ahead of every other
C++ toolchain.

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

On Windows the GameInput joystick and keyboard backends are built when the
Windows SDK in use has `gameinput.h`, as in SDL's own MSVC build. As upstream,
the static library honours the `SDL_DYNAMIC_API` environment variable.

## Dependency footprint on Linux

SDL compiles against the X11, Wayland, ALSA and xkbcommon headers only, so none
of those libraries is compiled or linked. libX11's headers include libxcb's,
and SDL's Vulkan renderer includes `xcb/xcb.h`; libxcb generates those headers
with Python, so a Linux build fetches a `rules_python` toolchain. On Bazel 7 the
libxcb module also raises `rules_python` and `protobuf` in a consumer's module
graph on every platform; Bazel 9 resolves newer versions of both anyway.

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
- As in SDL's own CI, `SDL_TESTS_QUICK=1` skips the slow, timing-sensitive
  parts of testatomic, testerror, testthread and testtimer, and testsem is
  built with `SDL_ASSERT_LEVEL=1`. Its 2 s wait comes back up to 150 ms late on
  macOS, which SDL's CI, building RelWithDebInfo, only logs.
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
