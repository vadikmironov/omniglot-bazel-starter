#!/usr/bin/env bash

# Wrapper around clang-format tool adapting command line arguments from rules_lint
# defined here:
# https://github.com/TimotheusBachinger/rules_lint/blob/main/format/private/formatter_binary.bzl#L48
# and here:
# https://github.com/TimotheusBachinger/rules_lint/blob/main/format/private/formatter_binary.bzl#L71
#

# --- begin runfiles.bash initialization v3 ---
# Copy-pasted from the Bazel Bash runfiles library v3.
set -uo pipefail
set +e
f=bazel_tools/tools/bash/runfiles/runfiles.bash
# shellcheck disable=SC1090
source "${RUNFILES_DIR:-/dev/null}/$f" 2>/dev/null ||
    source "$(grep -sm1 "^$f " "${RUNFILES_MANIFEST_FILE:-/dev/null}" | cut -f2- -d' ')" 2>/dev/null ||
    source "$0.runfiles/$f" 2>/dev/null ||
    source "$(grep -sm1 "^$f " "$0.runfiles_manifest" | cut -f2- -d' ')" 2>/dev/null ||
    source "$(grep -sm1 "^$f " "$0.exe.runfiles_manifest" | cut -f2- -d' ')" 2>/dev/null ||
    {
        echo >&2 "ERROR: cannot find $f"
        exit 1
    }
f=
set -e
# --- end runfiles.bash initialization v3 ---

# DEBUG BEGIN
#if [[ -f "${RUNFILES_REPO_MAPPING}" ]]; then
#    echo >&2 "*** DEBUG *** $(basename "${BASH_SOURCE[0]}") RUNFILES_REPO_MAPPING: ${RUNFILES_REPO_MAPPING}"
#    cat >&2 "${RUNFILES_REPO_MAPPING}"
#fi
# Enable debug for rlocation
#export RUNFILES_LIB_DEBUG=1
# DEBUG END

# argument copy to parse into clang_format binary
args=()
files=()

args+=("--style=file")
args+=("--fallback-style=none")

tool="llvm_toolchain_llvm/bin/clang-format"

# Get the clang-format binary from the runfiles
bin="$(rlocation $tool)" || {
    echo "ERROR: clang-format binary not found at $tool"
    exit 1
}

# Loop through all command line arguments
for arg in "$@"; do
    case "$arg" in
    --replace)
        args+=("-i")
        ;;
    --set-exit-if-changed)
        args+=("--Werror")
        ;;
    --dry-run)
        args+=("--dry-run")
        ;;
    *)
        files+=("$arg")
        ;;
    esac
done

time {
    printf "%s\0" "${files[@]}" | xargs --null "$bin" "${args[@]}" >&2
}
