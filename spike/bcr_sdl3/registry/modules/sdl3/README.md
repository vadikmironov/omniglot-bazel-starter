# sdl3

SDL 3 built from source with rules_cc, as a static library. `overlay/BUILD.bazel`
documents the port; below is what a consumer and a version bump need.

## Targets

- `@sdl3` (`SDL3::SDL3-static`), `@sdl3//:sdl3_headers` (`SDL3::Headers`),
  `@sdl3//:sdl3_test` (`SDL3::SDL3_test`).
- On macOS, declare `apple_support` before `rules_cc` in your `MODULE.bazel`:
  the Objective-C sources need its C++ toolchain, and toolchains register in
  `bazel_dep` order.

## Build configuration

Windows and Apple platforms use the configs SDL ships in `include/build_config/`.
Linux gets the one SDL's CMake configure would generate: `sdl3_config_checks.bzl`
mirrors the probes in `CMakeLists.txt` and `cmake/sdlchecks.cmake` with
`rules_cc_autoconf`, and `autoconf_hdr` fills upstream's
`SDL_build_config.h.cmake`. Backends without a Bazel module are off: PulseAudio,
PipeWire, JACK, sndio, KMSDRM, libdecor, D-Bus (portal dialogs, IME, screensaver
inhibition), libudev (hotplug and the HIDAPI hidraw backend), libusb, liburing,
GLX (OpenGL goes through EGL, as on Wayland), fribidi, libthai. X11, Wayland,
ALSA and xkbcommon are loaded at runtime by soname; their headers come from
the BCR modules pinned in `MODULE.bazel`.

## Tests

`test/BUILD.bazel` runs every non-interactive program from `test/CMakeLists.txt`
the way ctest does: dummy video and audio drivers, `SDL_ASSERT=abort`, plus the
no-SIMD reruns of testautomation and testplatform. Not reproduced: ctest's
`--trackmem` leak check, which is a regex over stdout.

## Upgrading

1. Diff `include/build_config/SDL_build_config.h.cmake` between the two
   releases. A new `#cmakedefine` needs a check in `sdl3_config_checks.bzl`, a
   removed one has a check to delete. A template entry with no check renders as
   `/* #undef NAME */` and a check with no entry is dropped, both silently:

   ```shell
   bazel build @sdl3//:config_h
   grep '#undef' bazel-bin/external/sdl3+/bazel/linux/SDL_build_config.h
   ```

   The expected `#undef` set is the Windows, Apple, console, BSD and
   optional-backend entries; anything else is a check to write.

2. Diff the `sdl_glob_sources`/`sdl_sources` calls in `CMakeLists.txt` against
   the source lists in `overlay/BUILD.bazel`; a new backend directory is a new
   glob. `wayland-protocols/*.xml` is globbed and needs nothing.

3. To confirm the Linux config against upstream, run SDL's own configure and
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
        <(grep '^#define' bazel-bin/external/sdl3+/bazel/linux/SDL_build_config.h | sort)
   ```

   Expected differences: `SDL_VIDEO_OPENGL_GLX` (CMake finds Mesa's
   `GL/glx.h`, the module has no GLX), the `SDL_DISABLE_<intrinsics>` lines
   (per CPU of the machine running CMake; the module leaves them to
   `SDL_intrin.h`), and the xkbcommon and libdecor version macros (the machine's
   packages against the pinned module).

4. `bazel run //tools:update_integrity -- sdl3 --version=<new>`, then the
   presubmit matrix. Windows ARM64 is in it because SDL's own MSVC build
   targets it and nothing here is x86-specific.
