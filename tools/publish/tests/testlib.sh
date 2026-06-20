#!/usr/bin/env bash
# Minimal shell test assertion library.

TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

pass() {
    ((TESTS_PASSED++)) || true
    ((TESTS_RUN++)) || true
    echo "  PASS: $1"
}

fail() {
    ((TESTS_FAILED++)) || true
    ((TESTS_RUN++)) || true
    echo "  FAIL: $1" >&2
    if [ -n "${2:-}" ]; then
        echo "    Expected: $2" >&2
        echo "    Actual:   ${3:-}" >&2
    fi
}

assert_equals() {
    local expected="$1"
    local actual="$2"
    local msg="${3:-assert_equals}"
    if [ "${expected}" = "${actual}" ]; then
        pass "${msg}"
    else
        fail "${msg}" "${expected}" "${actual}"
    fi
}

assert_contains() {
    local haystack="$1"
    local needle="$2"
    local msg="${3:-assert_contains}"
    if [[ "${haystack}" == *"${needle}"* ]]; then
        pass "${msg}"
    else
        fail "${msg}" "contains '${needle}'" "'${haystack}'"
    fi
}

assert_not_contains() {
    local haystack="$1"
    local needle="$2"
    local msg="${3:-assert_not_contains}"
    if [[ "${haystack}" != *"${needle}"* ]]; then
        pass "${msg}"
    else
        fail "${msg}" "does not contain '${needle}'" "'${haystack}'"
    fi
}

# Run a command and check its exit code.
# Usage: assert_exit_code <expected> <command> [args...]
assert_exit_code() {
    local expected="$1"
    shift
    local actual
    set +e
    "$@" >/dev/null 2>&1
    actual=$?
    set -e
    local cmd_str="$*"
    if [ "${expected}" = "${actual}" ]; then
        pass "exit code ${expected}: ${cmd_str}"
    else
        fail "exit code: ${cmd_str}" "${expected}" "${actual}"
    fi
}

test_summary() {
    echo ""
    echo "======================================="
    echo "Tests: ${TESTS_RUN} | Passed: ${TESTS_PASSED} | Failed: ${TESTS_FAILED}"
    echo "======================================="
    if [ "${TESTS_FAILED}" -gt 0 ]; then
        exit 1
    fi
}
