#!/usr/bin/env bash
set -euo pipefail

# Locate runfiles
if [[ -n "${TEST_SRCDIR:-}" ]]; then
    RUNFILES="${TEST_SRCDIR}/_main"
else
    RUNFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
fi

source "${RUNFILES}/tools/publish/tests/testlib.sh"
CRED_HELPER="${RUNFILES}/tools/publish/credential-helper"

TMPDIR_TEST=$(mktemp -d)
trap 'rm -rf "${TMPDIR_TEST}"' EXIT

# Helper: run credential-helper with a custom .netrc and JSON input.
# Args: netrc_content input_json
run_cred_helper() {
    local netrc_content="${1:-}"
    local input_json="$2"
    local test_home="${TMPDIR_TEST}/home_${RANDOM}"
    mkdir -p "${test_home}"
    if [ -n "${netrc_content}" ]; then
        printf '%b' "${netrc_content}" > "${test_home}/.netrc"
    fi
    echo "${input_json}" | HOME="${test_home}" bash "${CRED_HELPER}"
}

echo "=== Credential Helper Tests ==="

# --- Basic Functionality ---
echo ""
echo "--- Basic Functionality ---"

output=$(run_cred_helper "machine registry.invalid\n  login admin\n  password secret123" \
    '{"uri":"https://registry.invalid/v2/path"}')
assert_contains "${output}" "Authorization" "simple match returns auth header"
assert_contains "${output}" "Basic" "simple match returns Basic auth"

output=$(run_cred_helper "machine other.invalid\n  login admin\n  password secret123" \
    '{"uri":"https://registry.invalid/path"}')
assert_equals '{"headers":{}}' "${output}" "no match returns empty headers"

output=$(run_cred_helper "" '{"uri":"https://registry.invalid/path"}')
assert_equals '{"headers":{}}' "${output}" "no .netrc file returns empty headers"

output=$(run_cred_helper "machine registry.invalid\n  login admin\n  password secret123" \
    '{"foo":"bar"}')
assert_equals '{"headers":{}}' "${output}" "empty/missing URI returns empty headers"

# --- Multi-Machine Parsing ---
echo ""
echo "--- Multi-Machine Parsing ---"

output=$(run_cred_helper "machine a.invalid\n  login userA\n  password passA\nmachine b.invalid\n  login userB\n  password passB" \
    '{"uri":"https://b.invalid/path"}')
assert_contains "${output}" "Authorization" "multi-machine: correct entry selected"
# Decode and verify it's userB:passB
decoded=$(echo "${output}" | grep -o '"Basic [^"]*"' | sed 's/"Basic //;s/"//' | base64 -d 2>/dev/null || true)
assert_equals "userB:passB" "${decoded}" "multi-machine: correct credentials returned"

# --- Default Entry ---
echo ""
echo "--- Default Entry ---"

output=$(run_cred_helper "machine specific.invalid\n  login suser\n  password spass\ndefault\n  login duser\n  password dpass" \
    '{"uri":"https://unknown.invalid/path"}')
decoded=$(echo "${output}" | grep -o '"Basic [^"]*"' | sed 's/"Basic //;s/"//' | base64 -d 2>/dev/null || true)
assert_equals "duser:dpass" "${decoded}" "default entry used as fallback"

output=$(run_cred_helper "machine specific.invalid\n  login suser\n  password spass\ndefault\n  login duser\n  password dpass" \
    '{"uri":"https://specific.invalid/path"}')
decoded=$(echo "${output}" | grep -o '"Basic [^"]*"' | sed 's/"Basic //;s/"//' | base64 -d 2>/dev/null || true)
assert_equals "suser:spass" "${decoded}" "specific machine preferred over default"

# --- Format Variants ---
echo ""
echo "--- Format Variants ---"

output=$(run_cred_helper "machine registry.invalid login admin password secret123" \
    '{"uri":"https://registry.invalid/path"}')
assert_contains "${output}" "Authorization" "single-line format works"

output=$(run_cred_helper "# this is a comment\nmachine registry.invalid\n  login admin\n  # inline comment\n  password secret123" \
    '{"uri":"https://registry.invalid/path"}')
assert_contains "${output}" "Authorization" "comments are ignored"

# Empty .netrc
test_home="${TMPDIR_TEST}/home_empty"
mkdir -p "${test_home}"
touch "${test_home}/.netrc"
output=$(echo '{"uri":"https://registry.invalid/path"}' | HOME="${test_home}" bash "${CRED_HELPER}")
assert_equals '{"headers":{}}' "${output}" "empty .netrc returns empty headers"

# --- Edge Cases ---
echo ""
echo "--- Edge Cases ---"

output=$(run_cred_helper "machine registry.invalid\n  login admin" \
    '{"uri":"https://registry.invalid/path"}')
assert_equals '{"headers":{}}' "${output}" "login only (no password) returns empty"

output=$(run_cred_helper "machine registry.invalid\n  login admin\n  password secret123" \
    '{"uri":"https://registry.invalid:8080/path"}')
assert_contains "${output}" "Authorization" "URI with port: strips port and matches"

# --- Base64 Correctness ---
echo ""
echo "--- Base64 Correctness ---"

output=$(run_cred_helper "machine registry.invalid\n  login testuser\n  password testpass" \
    '{"uri":"https://registry.invalid/path"}')
decoded=$(echo "${output}" | grep -o '"Basic [^"]*"' | sed 's/"Basic //;s/"//' | base64 -d 2>/dev/null || true)
assert_equals "testuser:testpass" "${decoded}" "base64 decodes to login:password"

test_summary
