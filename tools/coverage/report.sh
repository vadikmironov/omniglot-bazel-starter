#!/usr/bin/env bash

# Renders the combined LCOV report to an HTML tree via the hermetic lcov genhtml.
#
# Prerequisite: produce the report first with
#   bazel coverage --combined_report=lcov //...
#
# Usage (run through Bazel):
#   bazel run //tools/coverage:report                 # defaults below
#   bazel run //tools/coverage:report -- REPORT OUTDIR
#
# REPORT defaults to the combined report under bazel-out; OUTDIR defaults to
# ./coverage-html in the workspace.

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

# The genhtml runfiles path is passed as the first argument via $(rlocationpath).
genhtml="$(rlocation "$1")" || {
    echo >&2 "ERROR: genhtml not found in runfiles: $1"
    exit 1
}
shift

workspace="${BUILD_WORKSPACE_DIRECTORY:-$PWD}"
report="${1:-${workspace}/bazel-out/_coverage/_coverage_report.dat}"
outdir="${2:-${workspace}/coverage-html}"

if [[ ! -s "${report}" ]]; then
    echo >&2 "ERROR: no combined LCOV report at: ${report}"
    echo >&2 "Run first: bazel coverage --combined_report=lcov //..."
    exit 1
fi

# genhtml resolves relative SF: paths against the current directory.
cd "${workspace}"
"${genhtml}" --output-directory "${outdir}" "${report}"
echo "Coverage HTML written to: ${outdir}/index.html"
