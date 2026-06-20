#!/usr/bin/env bash
# Rust lint gate: fail if rules_rust's captured clippy output is non-empty.
# clippy runs non-blocking (capture_clippy_output) so builds never fail on lint;
# this test is the red/green check. Prints the diagnostics on failure.
set -euo pipefail
if [ -s "$1" ]; then
    cat "$1" >&2
    exit 1
fi
