#!/usr/bin/env bash
# Regenerates the Linux SDL_build_config.h of the sdl3 overlay.
#
# SDL ships hand-written build configs for Windows and Apple platforms and
# generates the Linux one with CMake. This runs that CMake configure, on the
# SDL release tarball, inside an Ubuntu 20.04 container (the oldest glibc in
# BCR's presubmit, so nothing newer than glibc 2.31 gets detected), with the
# packages below installed and every feature that has no Bazel module
# switched off. The result is copied over the checked-in header verbatim,
# with a banner naming this script, plus one documented edit (GLX, see the
# end of this file).
#
#   tools/gen_linux_build_config.sh            # regenerate for 3.4.16
#   tools/gen_linux_build_config.sh 3.4.18     # for another version
#
# Needs docker. The spike workflow runs it and fails if the output differs
# from the checked-in file.
set -euo pipefail

inside=""
if [[ "${1:-}" == "--inside" ]]; then
    inside=1
    shift
fi
SDL_VERSION="${1:-3.4.16}"
IMAGE="ubuntu:20.04"
PACKAGES=(
    ca-certificates cmake curl gcc make pkg-config
    # X11 and Wayland: SDL needs the headers at build time and loads the
    # libraries at runtime. Same set as the BCR modules the overlay depends on;
    # no libxss-dev / libxtst-dev (Xscrnsaver, XTest), no libdecor-0-dev.
    libx11-dev libxext-dev libxcursor-dev libxi-dev libxfixes-dev libxrandr-dev
    libwayland-dev libxkbcommon-dev
    # ALSA headers, loaded at runtime too.
    libasound2-dev
    # Desktop OpenGL headers for the SDL_VIDEO_OPENGL check; EGL and GLES come
    # from the headers SDL vendors in src/video/khronos.
    libgl-dev
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
    -DSDL_HIDAPI=OFF
)

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out="$here/../registry/modules/sdl3/$SDL_VERSION/overlay/bazel/linux/SDL_build_config.h"

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
    # GLX needs GL/glx.h from Mesa, which is not a Bazel module; without it
    # SDL uses EGL for OpenGL on X11, as it does on Wayland.
    sed -e 's|^#define SDL_VIDEO_OPENGL_GLX 1$|/* #undef SDL_VIDEO_OPENGL_GLX */ /* Bazel: no Mesa headers, OpenGL over EGL */|' \
        "$generated"
    exit 0
fi

docker run --rm \
    -v "$here/$(basename "${BASH_SOURCE[0]}"):/gen.sh:ro" \
    "$IMAGE" bash /gen.sh --inside "$SDL_VERSION" > "$out.tmp"
mv "$out.tmp" "$out"
echo "wrote $out"
