#!/usr/bin/env bash
# Generates an oracle for the sdl3 overlay's Linux build config: what SDL's
# own CMake configure produces on a given Ubuntu image, for the module's
# autoconf-generated header to be diffed against. Spike tooling, not part of
# the module.
#
# Runs the CMake configure on the SDL release tarball inside the container,
# with the packages below installed and every feature that has no Bazel
# module switched off, and writes oracle/SDL_build_config.<image>.h with a
# banner naming this script, plus the two documented edits at the end of
# this file.
#
#   tools/gen_linux_build_config.sh                       # 3.4.16, ubuntu:20.04
#   tools/gen_linux_build_config.sh 3.4.16 ubuntu:24.04   # another image
#
# Needs docker. The spike workflow runs it for both images and fails if the
# output differs from the checked-in oracle.
set -euo pipefail

inside=""
if [[ "${1:-}" == "--inside" ]]; then
    inside=1
    shift
fi
SDL_VERSION="${1:-3.4.16}"
IMAGE="${2:-ubuntu:20.04}"
PACKAGES=(
    ca-certificates cmake curl gcc libc6-dev make pkg-config
    # X11 and Wayland: SDL needs the headers at build time and loads the
    # libraries at runtime. Same set as the BCR modules the overlay depends on;
    # no libxss-dev / libxtst-dev (Xscrnsaver, XTest), no libdecor-0-dev.
    libx11-dev libxext-dev libxcursor-dev libxi-dev libxfixes-dev libxrandr-dev
    libwayland-dev libxkbcommon-dev
    # ALSA headers, loaded at runtime too.
    libasound2-dev
    # Desktop OpenGL headers for the SDL_VIDEO_OPENGL check, and egl.pc, which
    # the Wayland check requires; the EGL and GLES headers themselves come
    # from the ones SDL vendors in src/video/khronos.
    libgl-dev libegl-dev
)
# Every SDL option that would otherwise probe the container for libraries
# that have no Bazel module, or that the overlay does not build.
CMAKE_FLAGS=(
    -DCMAKE_BUILD_TYPE=Release
    -DSDL_SHARED=OFF -DSDL_STATIC=ON
    -DSDL_TESTS=OFF -DSDL_EXAMPLES=OFF -DSDL_TEST_LIBRARY=OFF -DSDL_INSTALL=OFF
    -DSDL_ALSA=ON
    -DSDL_PULSEAUDIO=OFF -DSDL_PIPEWIRE=OFF -DSDL_JACK=OFF -DSDL_SNDIO=OFF -DSDL_OSS=OFF
    -DSDL_X11=ON -DSDL_X11_XSCRNSAVER=OFF -DSDL_X11_XTEST=OFF
    -DSDL_FRIBIDI=OFF -DSDL_LIBTHAI=OFF
    -DSDL_WAYLAND=ON -DSDL_WAYLAND_LIBDECOR=OFF
    -DSDL_KMSDRM=OFF -DSDL_OPENVR=OFF -DSDL_RPI=OFF -DSDL_ROCKCHIP=OFF -DSDL_VIVANTE=OFF
    -DSDL_OPENGL=ON -DSDL_OPENGLES=ON -DSDL_VULKAN=ON
    -DSDL_DBUS=OFF -DSDL_IBUS=OFF -DSDL_LIBUDEV=OFF -DSDL_LIBURING=OFF
    # HIDAPI stays on (the virtual joystick depends on it in CMake) but has no
    # backend here: the hidraw one needs libudev, and libusb is off.
    -DSDL_HIDAPI_LIBUSB=OFF
)

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out="$here/../oracle/SDL_build_config.${IMAGE//[:.]/}.h"

if [[ -n "$inside" ]]; then
    # Runs inside the container.
    export DEBIAN_FRONTEND=noninteractive
    apt-get -qq update >&2
    apt-get -qq install -y --no-install-recommends "${PACKAGES[@]}" >&2
    curl -sSL -o /tmp/sdl.tar.gz \
        "https://github.com/libsdl-org/SDL/releases/download/release-$SDL_VERSION/SDL3-$SDL_VERSION.tar.gz"
    tar -C /tmp -xzf /tmp/sdl.tar.gz
    cmake -S "/tmp/SDL3-$SDL_VERSION" -B /tmp/build "${CMAKE_FLAGS[@]}" >&2
    generated="/tmp/build/include-config-release/build_config/SDL_build_config.h"

    cat <<EOF
/*
  SDL build configuration for Linux, generated for the Bazel build by
  tools/gen_linux_build_config.sh from SDL $SDL_VERSION's own CMake configure:

    $IMAGE, $(cmake --version | head -1), $(gcc --version | head -1)
    packages: ${PACKAGES[*]}
    cmake ${CMAKE_FLAGS[*]}

  Do not edit; rerun the script.
*/
EOF
    # Two edits to CMake's output:
    # - GLX needs GL/glx.h from Mesa, which is not a Bazel module; without it
    #   SDL uses EGL for OpenGL on X11, as it does on Wayland.
    # - SDL_DISABLE_<intrinsics> records what the container's x86_64 compiler
    #   could not target (NEON, LoongArch). The header serves every CPU the
    #   module builds for, and SDL_intrin.h already selects intrinsics by
    #   the compiler's own feature macros, so the opt-outs are dropped.
    sed -E \
        -e 's,^#define SDL_VIDEO_OPENGL_GLX 1$,/* #undef SDL_VIDEO_OPENGL_GLX */ /* Bazel: no Mesa headers; OpenGL over EGL */,' \
        -e 's,^#define (SDL_DISABLE_(SSE|SSE2|SSE3|SSE4_1|SSE4_2|AVX|AVX2|AVX512F|MMX|LSX|LASX|NEON)) 1$,/* #undef \1 */ /* Bazel: per-CPU; SDL_intrin.h decides */,' \
        "$generated"
    exit 0
fi

mkdir -p "$(dirname "$out")"
docker run --rm \
    -v "$here/$(basename "${BASH_SOURCE[0]}"):/gen.sh:ro" \
    "$IMAGE" bash /gen.sh --inside "$SDL_VERSION" "$IMAGE" > "$out.tmp"
mv "$out.tmp" "$out"
echo "wrote $out"
