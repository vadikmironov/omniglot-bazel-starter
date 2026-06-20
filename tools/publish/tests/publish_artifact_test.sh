#!/usr/bin/env bash
set -euo pipefail

# Locate runfiles
if [[ -n "${TEST_SRCDIR:-}" ]]; then
    RUNFILES="${TEST_SRCDIR}/_main"
else
    RUNFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
fi

source "${RUNFILES}/tools/publish/tests/testlib.sh"
PUBLISH_SCRIPT="${RUNFILES}/tools/publish/publish_artifact.sh"

TMPDIR_TEST=$(mktemp -d)
trap 'rm -rf "${TMPDIR_TEST}"' EXIT

# Create dummy artifact
DUMMY_FILE="${TMPDIR_TEST}/sample_artifact.txt"
echo "test artifact content" > "${DUMMY_FILE}"

# Create a minimal valid wheel for PyPI tests (repackage_wheel.py requires a real wheel)
DUMMY_WHEEL="${TMPDIR_TEST}/test_pkg-0.0.0-py3-none-any.whl"
python3 -c "
import zipfile, csv, hashlib, base64, io
dist_info = 'test_pkg-0.0.0.dist-info'
entries = {
    'test_pkg/__init__.py': b'# test\n',
    dist_info + '/METADATA': b'Metadata-Version: 2.1\nName: test_pkg\nVersion: 0.0.0\n',
    dist_info + '/WHEEL': b'Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
}
buf = io.StringIO()
w = csv.writer(buf, lineterminator='\n')
for name, data in entries.items():
    h = 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
    w.writerow((name, h, str(len(data))))
w.writerow((dist_info + '/RECORD', '', ''))
entries[dist_info + '/RECORD'] = buf.getvalue().encode()
with zipfile.ZipFile('${DUMMY_WHEEL}', 'w', zipfile.ZIP_DEFLATED) as zf:
    for name, data in entries.items():
        zf.writestr(name, data)
"

# ---------------------------------------------------------------------------
# Helper: run publish_artifact.sh with DRY_RUN and PUBLISH_VERSION
# Args: extra_env_string mode [remaining publish_artifact.sh args...]
# Returns combined stdout+stderr. Exit code saved in LAST_EXIT_CODE.
# ---------------------------------------------------------------------------
LAST_EXIT_CODE=0

run_publish() {
    local extra_env_str="$1"
    shift
    local -a env_vars=(
        DRY_RUN=1
        PUBLISH_URL=https://test.invalid
        PUBLISH_PLATFORM=artifactory
        PUBLISH_VERSION=1.0.0
    )
    if [ -n "${extra_env_str}" ]; then
        read -ra extra_pairs <<< "${extra_env_str}"
        env_vars+=("${extra_pairs[@]}")
    fi
    local exit_code=0
    set +e
    LAST_EXIT_CODE=0
    local output
    output=$(env "${env_vars[@]}" bash "${PUBLISH_SCRIPT}" "$@" 2>&1)
    exit_code=$?
    set -e
    LAST_EXIT_CODE=${exit_code}
    echo "${output}"
}

# Helper for validation tests (no DRY_RUN, expects failure)
run_publish_raw() {
    local extra_env_str="$1"
    shift
    local -a env_vars=()
    if [ -n "${extra_env_str}" ]; then
        read -ra extra_pairs <<< "${extra_env_str}"
        env_vars+=("${extra_pairs[@]}")
    fi
    local exit_code=0
    set +e
    local output
    output=$(env "${env_vars[@]}" bash "${PUBLISH_SCRIPT}" "$@" 2>&1)
    exit_code=$?
    set -e
    LAST_EXIT_CODE=${exit_code}
    echo "${output}"
}

echo "=== Publish Artifact Tests ==="

# =========================================================================
# Version / PUBLISH_MODE
# =========================================================================
echo ""
echo "--- Version / PUBLISH_MODE ---"

output=$(run_publish "" \
    maven test-repo "${DUMMY_FILE}" \
    com.test test-artifact '' jar)
assert_contains "${output}" "Resolved version: 1.0.0" "PUBLISH_VERSION used directly"

output=$(run_publish "PUBLISH_VERSION=99.99.99" \
    maven test-repo "${DUMMY_FILE}" \
    com.test test-artifact '' jar)
assert_contains "${output}" "Resolved version: 99.99.99" "PUBLISH_VERSION override"

# PUBLISH_MODE=dev + maven → SNAPSHOT suffix
output=$(run_publish "PUBLISH_MODE=dev" \
    maven test-repo "${DUMMY_FILE}" \
    com.test test-artifact '' jar)
assert_contains "${output}" "Resolved version: 1.0.0-SNAPSHOT" "dev mode maven gets SNAPSHOT"

# PUBLISH_MODE=dev + pypi → no suffix
output=$(run_publish "PUBLISH_MODE=dev" \
    pypi pypi-local "${DUMMY_WHEEL}" \
    '' test_pkg '' whl)
assert_not_contains "${output}" "SNAPSHOT" "dev mode pypi no SNAPSHOT"

# PUBLISH_MODE=dev + generic → no suffix
output=$(run_publish "PUBLISH_MODE=dev" \
    generic generic-repo "${DUMMY_FILE}" \
    '' my-pkg '' '')
assert_not_contains "${output}" "SNAPSHOT" "dev mode generic no SNAPSHOT"

# PUBLISH_MODE=release + maven → no suffix
output=$(run_publish "PUBLISH_MODE=release" \
    maven test-repo "${DUMMY_FILE}" \
    com.test test-artifact '' jar)
assert_contains "${output}" "Resolved version: 1.0.0" "release mode no SNAPSHOT"
assert_not_contains "${output}" "SNAPSHOT" "release mode maven no SNAPSHOT"

# Empty PUBLISH_MODE (backward compat) → no suffix
output=$(run_publish "PUBLISH_MODE=" \
    maven test-repo "${DUMMY_FILE}" \
    com.test test-artifact '' jar)
assert_not_contains "${output}" "SNAPSHOT" "empty PUBLISH_MODE no SNAPSHOT"

# Missing PUBLISH_VERSION fails
run_publish_raw "PUBLISH_URL=https://test.invalid DRY_RUN=1" \
    maven test-repo "${DUMMY_FILE}" \
    com.test test-artifact '' jar > /dev/null 2>&1 || true
assert_equals "1" "${LAST_EXIT_CODE}" "missing PUBLISH_VERSION fails"

# =========================================================================
# URL Construction — Maven
# =========================================================================
echo ""
echo "--- URL Construction: Maven ---"

output=$(run_publish "" \
    maven libs-release "${DUMMY_FILE}" \
    com.monorepo.test my-lib '' zip)
assert_contains "${output}" "https://test.invalid/libs-release/com/monorepo/test/my-lib/1.0.0/my-lib-1.0.0.zip" \
    "artifactory maven URL"

output=$(run_publish "PUBLISH_PLATFORM=gitea PUBLISH_OWNER=myorg" \
    maven libs-release "${DUMMY_FILE}" \
    com.monorepo.test my-lib '' zip)
assert_contains "${output}" "https://test.invalid/api/packages/myorg/maven/com/monorepo/test/my-lib/1.0.0/my-lib-1.0.0.zip" \
    "gitea maven URL"

output=$(run_publish "PUBLISH_PLATFORM=nexus" \
    maven libs-release "${DUMMY_FILE}" \
    com.monorepo.test my-lib '' zip)
assert_contains "${output}" "https://test.invalid/repository/libs-release/com/monorepo/test/my-lib/1.0.0/my-lib-1.0.0.zip" \
    "nexus maven URL"

output=$(run_publish "PUBLISH_URL=https://test.invalid/" \
    maven libs-release "${DUMMY_FILE}" \
    com.monorepo.test my-lib '' zip)
assert_contains "${output}" "https://test.invalid/libs-release/" \
    "trailing slash in PUBLISH_URL stripped"
assert_not_contains "${output}" "//libs-release" \
    "no double slash from trailing PUBLISH_URL"

output=$(run_publish "" \
    maven libs-release "${DUMMY_FILE}" \
    com.test my-app linux-x86_64 zip)
assert_contains "${output}" "my-app-1.0.0-linux-x86_64.zip" \
    "maven URL with classifier"

# =========================================================================
# URL Construction — Generic
# =========================================================================
echo ""
echo "--- URL Construction: Generic ---"

output=$(run_publish "" \
    generic generic-repo "${DUMMY_FILE}" \
    '' my-pkg '' '')
assert_contains "${output}" "https://test.invalid/generic-repo/my-pkg/1.0.0/" \
    "artifactory generic URL"

output=$(run_publish "PUBLISH_PLATFORM=nexus" \
    generic generic-repo "${DUMMY_FILE}" \
    '' my-pkg '' '')
assert_contains "${output}" "https://test.invalid/repository/generic-repo/my-pkg/1.0.0/" \
    "nexus generic URL"

output=$(run_publish "PUBLISH_PLATFORM=gitea PUBLISH_OWNER=myorg" \
    generic generic-repo "${DUMMY_FILE}" \
    '' my-pkg '' '')
assert_contains "${output}" "https://test.invalid/api/packages/myorg/generic/my-pkg/1.0.0/" \
    "gitea generic URL"

# =========================================================================
# URL Construction — PyPI
# =========================================================================
echo ""
echo "--- URL Construction: PyPI ---"

output=$(run_publish "" \
    pypi pypi-local "${DUMMY_WHEEL}" \
    '' test_pkg '' whl)
assert_contains "${output}" "https://test.invalid/pypi-local/" \
    "artifactory pypi URL"

output=$(run_publish "PUBLISH_PLATFORM=nexus" \
    pypi pypi-local "${DUMMY_WHEEL}" \
    '' test_pkg '' whl)
assert_contains "${output}" "https://test.invalid/repository/pypi-local/" \
    "nexus pypi URL"

output=$(run_publish "PUBLISH_PLATFORM=gitea PUBLISH_OWNER=myorg" \
    pypi pypi-local "${DUMMY_WHEEL}" \
    '' test_pkg '' whl)
assert_contains "${output}" "https://test.invalid/api/packages/myorg/pypi" \
    "gitea pypi URL"

# =========================================================================
# PyPI Wheel Repackaging
# =========================================================================
echo ""
echo "--- PyPI Wheel Repackaging ---"

output=$(run_publish "PUBLISH_VERSION=2.5.0" \
    pypi pypi-local "${DUMMY_WHEEL}" \
    '' test_pkg '' whl)
assert_contains "${output}" "Repackaged wheel:" "pypi repackaging runs"
assert_contains "${output}" "test_pkg-2.5.0-py3-none-any.whl" "repackaged filename has new version"
assert_not_contains "${output}" "0.0.0" "placeholder version replaced"

# Dev version with local identifier
output=$(run_publish "PUBLISH_VERSION=1.0.0.dev3+abc" \
    pypi pypi-local "${DUMMY_WHEEL}" \
    '' test_pkg '' whl)
assert_contains "${output}" "Repackaged wheel:" "dev version repackaging runs"
assert_contains "${output}" "1.0.0.dev3+abc" "dev version in repackaged filename"

# =========================================================================
# Input Validation
# =========================================================================
echo ""
echo "--- Input Validation ---"

run_publish_raw "PUBLISH_URL= PUBLISH_VERSION=1.0.0" \
    maven test-repo "${DUMMY_FILE}" \
    com.test test-artifact '' jar > /dev/null 2>&1 || true
assert_equals "1" "${LAST_EXIT_CODE}" "missing PUBLISH_URL fails"

run_publish_raw "PUBLISH_URL=https://test.invalid PUBLISH_PLATFORM=gitea PUBLISH_OWNER= PUBLISH_VERSION=1.0.0" \
    maven test-repo "${DUMMY_FILE}" \
    com.test test-artifact '' jar > /dev/null 2>&1 || true
assert_equals "1" "${LAST_EXIT_CODE}" "gitea without owner fails"

run_publish_raw "PUBLISH_URL=https://test.invalid DRY_RUN=1 PUBLISH_VERSION=1.0.0" \
    maven test-repo "/nonexistent/file.zip" \
    com.test test-artifact '' jar > /dev/null 2>&1 || true
assert_equals "1" "${LAST_EXIT_CODE}" "file not found fails"

run_publish_raw "PUBLISH_URL=https://test.invalid DRY_RUN=1 PUBLISH_VERSION=1.0.0" \
    npm test-repo "${DUMMY_FILE}" \
    '' '' '' '' > /dev/null 2>&1 || true
assert_equals "1" "${LAST_EXIT_CODE}" "unknown mode fails"

run_publish_raw "PUBLISH_URL=https://test.invalid DRY_RUN=1 PUBLISH_VERSION=1.0.0" \
    maven test-repo "${DUMMY_FILE}" \
    '' '' '' jar > /dev/null 2>&1 || true
assert_equals "1" "${LAST_EXIT_CODE}" "maven missing group_id fails"

run_publish_raw "PUBLISH_URL=https://test.invalid DRY_RUN=1 PUBLISH_VERSION=1.0.0" \
    generic test-repo "${DUMMY_FILE}" \
    '' '' '' '' > /dev/null 2>&1 || true
assert_equals "1" "${LAST_EXIT_CODE}" "generic missing artifact_id fails"

# =========================================================================
# DRY_RUN Output
# =========================================================================
echo ""
echo "--- DRY_RUN Output ---"

output=$(run_publish "" \
    maven libs-release "${DUMMY_FILE}" \
    com.test my-lib '' zip)
assert_contains "${output}" "DRY RUN:" "DRY RUN message present in maven mode"
assert_contains "${output}" "DRY RUN: would upload POM" "DRY RUN POM message for non-jar"
assert_contains "${output}" "SHA-256:" "SHA-256 checksum printed in maven mode"

output=$(run_publish "" \
    maven libs-release "${DUMMY_FILE}" \
    com.test my-lib '' jar)
assert_not_contains "${output}" "POM" "no POM message for jar packaging"

# =========================================================================
# Retry Logic
# =========================================================================
echo ""
echo "--- Retry Logic ---"

# Stateful mock curl that returns HTTP codes from a sequence file.
# Each call reads the next code; if exhausted, repeats the last one.
MOCK_BIN_RETRY="${TMPDIR_TEST}/mock_bin_retry"
mkdir -p "${MOCK_BIN_RETRY}"

RETRY_COUNTER="${TMPDIR_TEST}/retry_counter"
RETRY_CODES="${TMPDIR_TEST}/retry_codes"

cat > "${MOCK_BIN_RETRY}/curl" << 'CURLEOF'
#!/usr/bin/env bash
# Stateful mock: reads next HTTP code from $RETRY_CODES file
COUNTER_FILE="${RETRY_COUNTER}"
CODES_FILE="${RETRY_CODES}"
count=$(cat "${COUNTER_FILE}" 2>/dev/null || echo "0")
count=$((count + 1))
echo "${count}" > "${COUNTER_FILE}"
# Read all codes into array
mapfile -t codes < "${CODES_FILE}"
idx=$((count - 1))
if [ "${idx}" -ge "${#codes[@]}" ]; then
    idx=$(( ${#codes[@]} - 1 ))
fi
echo "${codes[$idx]}"
CURLEOF
chmod +x "${MOCK_BIN_RETRY}/curl"

# Helper: run publish with retry mock (no DRY_RUN, instant retries)
# Args: codes_string extra_env_str [publish_artifact.sh args...]
#   codes_string: newline-separated HTTP codes (e.g., "503\n200")
run_publish_retry() {
    local codes_str="$1"
    local extra_env_str="$2"
    shift 2
    # Reset counter and write code sequence
    echo "0" > "${RETRY_COUNTER}"
    printf '%b\n' "${codes_str}" > "${RETRY_CODES}"
    local -a env_vars=(
        PATH="${MOCK_BIN_RETRY}:${PATH}"
        PUBLISH_URL=https://test.invalid
        PUBLISH_PLATFORM=artifactory
        PUBLISH_RETRY_DELAY=0
        PUBLISH_VERSION=1.0.0
        RETRY_COUNTER="${RETRY_COUNTER}"
        RETRY_CODES="${RETRY_CODES}"
    )
    if [ -n "${extra_env_str}" ]; then
        read -ra extra_pairs <<< "${extra_env_str}"
        env_vars+=("${extra_pairs[@]}")
    fi
    local exit_code=0
    set +e
    LAST_EXIT_CODE=0
    local output
    output=$(env "${env_vars[@]}" bash "${PUBLISH_SCRIPT}" "$@" 2>&1)
    exit_code=$?
    set -e
    LAST_EXIT_CODE=${exit_code}
    echo "${output}"
}

RETRY_OUTPUT="${TMPDIR_TEST}/retry_output"

# Test: transient 503 then success on second attempt
run_publish_retry "503\n200" "" \
    maven test-repo "${DUMMY_FILE}" \
    com.test test-artifact '' jar > "${RETRY_OUTPUT}" 2>&1 || true
output=$(cat "${RETRY_OUTPUT}")
assert_equals "0" "${LAST_EXIT_CODE}" "retry: 503 then 200 succeeds"
assert_contains "${output}" "Upload successful" "retry: success message after retry"
assert_contains "${output}" "retrying" "retry: retry message printed"

# Test: all retries exhausted (3x 503)
run_publish_retry "503\n503\n503" "" \
    maven test-repo "${DUMMY_FILE}" \
    com.test test-artifact '' jar > "${RETRY_OUTPUT}" 2>&1 || true
output=$(cat "${RETRY_OUTPUT}")
assert_equals "1" "${LAST_EXIT_CODE}" "retry: 3x 503 exhausts retries"
assert_contains "${output}" "Upload failed" "retry: failure message after exhaustion"

# Test: no retry on client error (401)
run_publish_retry "401" "" \
    maven test-repo "${DUMMY_FILE}" \
    com.test test-artifact '' jar > "${RETRY_OUTPUT}" 2>&1 || true
output=$(cat "${RETRY_OUTPUT}")
assert_equals "1" "${LAST_EXIT_CODE}" "retry: 401 fails immediately"
assert_not_contains "${output}" "retrying" "retry: no retry on 401"
curl_calls=$(cat "${RETRY_COUNTER}")
assert_equals "1" "${curl_calls}" "retry: curl called exactly once on 401"

# Test: success on first attempt — no retry messages
run_publish_retry "200" "" \
    maven test-repo "${DUMMY_FILE}" \
    com.test test-artifact '' jar > "${RETRY_OUTPUT}" 2>&1 || true
output=$(cat "${RETRY_OUTPUT}")
assert_equals "0" "${LAST_EXIT_CODE}" "retry: 200 succeeds immediately"
assert_not_contains "${output}" "retrying" "retry: no retry messages on success"

# Test: PUBLISH_RETRIES=1 disables retry
run_publish_retry "503" "PUBLISH_RETRIES=1" \
    maven test-repo "${DUMMY_FILE}" \
    com.test test-artifact '' jar > "${RETRY_OUTPUT}" 2>&1 || true
output=$(cat "${RETRY_OUTPUT}")
assert_equals "1" "${LAST_EXIT_CODE}" "retry: RETRIES=1 fails after one attempt"
assert_not_contains "${output}" "retrying" "retry: no retry with RETRIES=1"
curl_calls=$(cat "${RETRY_COUNTER}")
assert_equals "1" "${curl_calls}" "retry: curl called once with RETRIES=1"

# =========================================================================
# Curl Error Handling
# =========================================================================
echo ""
echo "--- Curl Error Handling ---"

# Mock curl that simulates a .netrc error (curl exit code 26)
MOCK_BIN_CURL_ERR="${TMPDIR_TEST}/mock_bin_curl_err"
mkdir -p "${MOCK_BIN_CURL_ERR}"

cat > "${MOCK_BIN_CURL_ERR}/curl" << 'CURLEOF'
#!/usr/bin/env bash
echo "curl: (26) .netrc error: no such file" >&2
echo "000"
exit 26
CURLEOF
chmod +x "${MOCK_BIN_CURL_ERR}/curl"

CURL_ERR_OUTPUT="${TMPDIR_TEST}/curl_err_output"

run_publish_curl_err() {
    local extra_env_str="$1"
    shift
    local -a env_vars=(
        PATH="${MOCK_BIN_CURL_ERR}:${PATH}"
        PUBLISH_URL=https://test.invalid
        PUBLISH_PLATFORM=artifactory
        PUBLISH_RETRY_DELAY=0
        PUBLISH_VERSION=1.0.0
    )
    if [ -n "${extra_env_str}" ]; then
        read -ra extra_pairs <<< "${extra_env_str}"
        env_vars+=("${extra_pairs[@]}")
    fi
    set +e
    LAST_EXIT_CODE=0
    env "${env_vars[@]}" bash "${PUBLISH_SCRIPT}" "$@" > "${CURL_ERR_OUTPUT}" 2>&1
    LAST_EXIT_CODE=$?
    set -e
}

# Test: .netrc error shows clear message and does not retry
run_publish_curl_err "" \
    maven test-repo "${DUMMY_FILE}" \
    com.test test-artifact '' jar
output=$(cat "${CURL_ERR_OUTPUT}")
assert_equals "1" "${LAST_EXIT_CODE}" "curl-err: .netrc error fails"
assert_contains "${output}" ".netrc" "curl-err: error mentions .netrc"
assert_not_contains "${output}" "retrying" "curl-err: no retry on config error"
assert_contains "${output}" "Hint" "curl-err: shows actionable hint"

test_summary
