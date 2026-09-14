#!/usr/bin/env bash
# Diffs the #define set of the module's autoconf-generated Linux config
# against a CMake oracle from tools/gen_linux_build_config.sh. Spike tooling.
#
#   tools/diff_config.sh <generated SDL_build_config.h> <oracle header>
#
# Only `#define` lines count: the oracle keeps CMake's `/* #undef X */`
# comments and autoconf writes its own, and neither reaches the compiler.
# The xkbcommon and libdecor version macros are excluded: the oracle records
# the container's packages, the module the xkbcommon it pins in MODULE.bazel.
set -euo pipefail

generated="$1"
oracle="$2"

defines() {
    grep -E '^#define ' "$1" \
        | grep -vE '^#define SDL_(XKBCOMMON|LIBDECOR)_VERSION_' \
        | sed -E 's/[[:space:]]+/ /g; s/ $//' \
        | sort
}

if diff <(defines "$oracle") <(defines "$generated"); then
    echo "define sets are identical ($(defines "$oracle" | wc -l) defines)"
else
    echo "::error::the generated config differs from the oracle ($oracle): < oracle only, > generated only" >&2
    exit 1
fi
