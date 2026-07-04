#!/usr/bin/env bash

# Smoke test for the hermetic lcov genhtml renderer (//tools/coverage:report's
# engine). Runs genhtml on a checked-in LCOV fixture and asserts it produces an
# HTML report with the expected coverage summary. Guards the fragile external
# chain — rules_perl + the pinned lcov archive + genhtml — against Renovate bumps
# and toolchain changes that would silently break report rendering.
#
# Args (passed from BUILD via $(rlocationpath ...)):
#   $1  genhtml binary
#   $2  LCOV fixture (.lcov)

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

genhtml="$(rlocation "$1")" || {
    echo >&2 "ERROR: genhtml not found in runfiles: $1"
    exit 1
}
fixture="$(rlocation "$2")" || {
    echo >&2 "ERROR: fixture not found in runfiles: $2"
    exit 1
}

outdir="${TEST_TMPDIR:-$(mktemp -d)}/html"

# --ignore-errors source: the fixture ships no source tree, so genhtml warns on
# the missing SF file but still renders the summary from the LCOV line counts.
"${genhtml}" --ignore-errors source --output-directory "${outdir}" "${fixture}"

index="${outdir}/index.html"
[[ -s "${index}" ]] || {
    echo >&2 "FAIL: genhtml produced no index.html at ${index}"
    exit 1
}

fail=0
assert_contains() {
    if ! grep -qF "$1" "${index}"; then
        echo >&2 "FAIL: expected index.html to contain: $1"
        fail=1
    fi
}

# The report banner and the fixture's 2-of-4 (50%) line coverage must render.
assert_contains "LCOV - code coverage report"
assert_contains "50.0"

if [[ "${fail}" -ne 0 ]]; then
    echo >&2 "--- index.html ---"
    cat >&2 "${index}"
    exit 1
fi

echo "PASS: genhtml rendered ${index}"
