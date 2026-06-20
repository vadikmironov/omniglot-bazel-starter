#!/usr/bin/env bash
#
# Platform-agnostic artifact upload script with composable version resolution.
#
# Usage:
#   publish_artifact.sh <mode> <repo_name> <file_path> \
#       [<group_id> <artifact_id> <classifier> <packaging>]
#
# Arguments:
#   mode             - Upload mode: maven, pypi, generic
#   repo_name        - Repository name (e.g., libs-release-local, pypi-local)
#   file_path        - Path to the artifact file
#   group_id         - Maven group ID (maven mode)
#   artifact_id      - Maven artifact ID (maven/generic mode)
#   classifier       - Maven classifier, e.g., linux-x86_64 (maven mode, optional)
#   packaging        - File extension/type: jar, zip, whl (maven mode)
#
# Environment variables:
#   PUBLISH_VERSION          - Version string (required — set by mint or manually)
#   PUBLISH_MODE             - Publish mode: "dev" or "release" (optional, from mint)
#   PUBLISH_URL              - Base URL of the package registry (required)
#   PUBLISH_PLATFORM         - Platform type: "artifactory" (default), "nexus", or "gitea"
#   PUBLISH_OWNER            - Package owner/namespace (required for Gitea)
#   PUBLISH_RETRIES          - Max upload attempts (default: 3)
#   PUBLISH_RETRY_DELAY      - Initial retry delay in seconds (default: 2, doubles each attempt)
#
set -euo pipefail

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------
MODE="${1:?Usage: publish_artifact.sh <mode> <repo_name> <file_path> [<group_id> <artifact_id> <classifier> <packaging>]}"
REPO_NAME="${2:?Missing repo_name}"
FILE_PATH="${3:?Missing file_path}"
GROUP_ID="${4:-}"
ARTIFACT_ID="${5:-}"
CLASSIFIER="${6:-}"
PACKAGING="${7:-}"

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
PUBLISH_URL="${PUBLISH_URL:?PUBLISH_URL environment variable is required}"
PUBLISH_URL="${PUBLISH_URL%/}"  # Strip trailing slash to avoid double-slash in URLs
PUBLISH_PLATFORM="${PUBLISH_PLATFORM:-artifactory}"
PUBLISH_OWNER="${PUBLISH_OWNER:-}"
DRY_RUN="${DRY_RUN:-}"
_REPACKAGE_TMPDIR=""

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
if [ ! -f "${FILE_PATH}" ]; then
    echo "ERROR: File not found: ${FILE_PATH}" >&2
    exit 1
fi

if [ "${PUBLISH_PLATFORM}" = "gitea" ] && [ -z "${PUBLISH_OWNER}" ]; then
    echo "ERROR: PUBLISH_OWNER is required for Gitea platform" >&2
    exit 1
fi

FILENAME=$(basename "${FILE_PATH}")

# ---------------------------------------------------------------------------
# Version resolution
# ---------------------------------------------------------------------------
VERSION="${PUBLISH_VERSION:?PUBLISH_VERSION is required. Use mint or set it directly.}"
PUBLISH_MODE="${PUBLISH_MODE:-}"

# Append -SNAPSHOT for Maven dev builds (standard Maven convention)
if [ "${PUBLISH_MODE}" = "dev" ] && [ "${MODE}" = "maven" ]; then
    VERSION="${VERSION}-SNAPSHOT"
fi

echo "Resolved version: ${VERSION}"

# ---------------------------------------------------------------------------
# URL construction helpers
# ---------------------------------------------------------------------------

# Convert Maven group ID to path (com.monorepo.test -> com/monorepo/test)
group_to_path() {
    echo "$1" | tr '.' '/'
}

# Build Maven upload URL based on platform
maven_url() {
    local group_path
    group_path=$(group_to_path "${GROUP_ID}")

    local artifact_filename="${ARTIFACT_ID}-${VERSION}"
    if [ -n "${CLASSIFIER}" ]; then
        artifact_filename="${artifact_filename}-${CLASSIFIER}"
    fi
    artifact_filename="${artifact_filename}.${PACKAGING}"

    case "${PUBLISH_PLATFORM}" in
        artifactory)
            echo "${PUBLISH_URL}/${REPO_NAME}/${group_path}/${ARTIFACT_ID}/${VERSION}/${artifact_filename}"
            ;;
        nexus)
            echo "${PUBLISH_URL}/repository/${REPO_NAME}/${group_path}/${ARTIFACT_ID}/${VERSION}/${artifact_filename}"
            ;;
        gitea)
            echo "${PUBLISH_URL}/api/packages/${PUBLISH_OWNER}/maven/${group_path}/${ARTIFACT_ID}/${VERSION}/${artifact_filename}"
            ;;
        *)
            echo "ERROR: Unknown platform: ${PUBLISH_PLATFORM}" >&2
            exit 1
            ;;
    esac
}

# Build generic upload URL based on platform
generic_url() {
    case "${PUBLISH_PLATFORM}" in
        artifactory)
            echo "${PUBLISH_URL}/${REPO_NAME}/${ARTIFACT_ID}/${VERSION}/${FILENAME}"
            ;;
        nexus)
            echo "${PUBLISH_URL}/repository/${REPO_NAME}/${ARTIFACT_ID}/${VERSION}/${FILENAME}"
            ;;
        gitea)
            echo "${PUBLISH_URL}/api/packages/${PUBLISH_OWNER}/generic/${ARTIFACT_ID}/${VERSION}/${FILENAME}"
            ;;
        *)
            echo "ERROR: Unknown platform: ${PUBLISH_PLATFORM}" >&2
            exit 1
            ;;
    esac
}

# ---------------------------------------------------------------------------
# POM generation for Maven uploads (non-Java artifacts)
# ---------------------------------------------------------------------------
generate_pom() {
    local pom_file="${FILE_PATH}.pom"
    cat > "${pom_file}" <<POMEOF
<?xml version="1.0" encoding="UTF-8"?>
<project xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd"
    xmlns="http://maven.apache.org/POM/4.0.0"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <modelVersion>4.0.0</modelVersion>
  <groupId>${GROUP_ID}</groupId>
  <artifactId>${ARTIFACT_ID}</artifactId>
  <version>${VERSION}</version>
  <packaging>${PACKAGING}</packaging>
</project>
POMEOF
    echo "${pom_file}"
}

# Build POM upload URL
pom_url() {
    local group_path
    group_path=$(group_to_path "${GROUP_ID}")
    local pom_filename="${ARTIFACT_ID}-${VERSION}.pom"

    case "${PUBLISH_PLATFORM}" in
        artifactory)
            echo "${PUBLISH_URL}/${REPO_NAME}/${group_path}/${ARTIFACT_ID}/${VERSION}/${pom_filename}"
            ;;
        nexus)
            echo "${PUBLISH_URL}/repository/${REPO_NAME}/${group_path}/${ARTIFACT_ID}/${VERSION}/${pom_filename}"
            ;;
        gitea)
            echo "${PUBLISH_URL}/api/packages/${PUBLISH_OWNER}/maven/${group_path}/${ARTIFACT_ID}/${VERSION}/${pom_filename}"
            ;;
        *)
            echo "ERROR: Unknown platform: ${PUBLISH_PLATFORM}" >&2
            exit 1
            ;;
    esac
}

# ---------------------------------------------------------------------------
# Checksum computation (portable: Linux sha256sum / macOS shasum)
# ---------------------------------------------------------------------------
compute_sha256() {
    local file="$1"
    if command -v sha256sum &>/dev/null; then
        sha256sum "${file}" | awk '{print $1}'
    elif command -v shasum &>/dev/null; then
        shasum -a 256 "${file}" | awk '{print $1}'
    else
        echo ""
    fi
}

# ---------------------------------------------------------------------------
# Upload with retry
# ---------------------------------------------------------------------------
PUBLISH_RETRIES="${PUBLISH_RETRIES:-3}"
PUBLISH_RETRY_DELAY="${PUBLISH_RETRY_DELAY:-2}"

_CURL_STDERR=$(mktemp)
trap 'rm -f "${_CURL_STDERR}"; [ -n "${_REPACKAGE_TMPDIR}" ] && rm -rf "${_REPACKAGE_TMPDIR}"' EXIT

# HTTP codes that indicate a transient failure worth retrying.
_is_retryable() {
    local code="$1"
    case "${code}" in
        000|408|429|500|502|503|504) return 0 ;;
        *) return 1 ;;
    esac
}

# Curl exit codes that indicate non-transient configuration errors.
_is_curl_config_error() {
    local exit_code="$1"
    case "${exit_code}" in
        1|2|3|4|26|27|43|48) return 0 ;;
        *) return 1 ;;
    esac
}

# Run a curl upload with exponential-backoff retry.
# Usage: curl_upload_with_retry [curl_args...]
# Returns: HTTP status code via UPLOAD_HTTP_CODE variable.
curl_upload_with_retry() {
    local attempt=1
    local delay="${PUBLISH_RETRY_DELAY}"
    local curl_exit=0
    UPLOAD_HTTP_CODE=000
    UPLOAD_CURL_ERROR=""

    while [ "${attempt}" -le "${PUBLISH_RETRIES}" ]; do
        curl_exit=0
        UPLOAD_HTTP_CODE=$(curl --netrc --silent --show-error \
            --output /dev/null --write-out "%{http_code}" \
            "$@" 2>"${_CURL_STDERR}") || curl_exit=$?

        if [ -s "${_CURL_STDERR}" ]; then
            UPLOAD_CURL_ERROR=$(<"${_CURL_STDERR}")
        else
            UPLOAD_CURL_ERROR=""
        fi

        # Configuration errors (e.g., missing .netrc) won't resolve on retry
        if [ "${curl_exit}" -ne 0 ] && _is_curl_config_error "${curl_exit}"; then
            return 0
        fi

        if ! _is_retryable "${UPLOAD_HTTP_CODE}"; then
            return 0
        fi

        if [ "${attempt}" -lt "${PUBLISH_RETRIES}" ]; then
            local msg="HTTP ${UPLOAD_HTTP_CODE}"
            [ -n "${UPLOAD_CURL_ERROR}" ] && msg="${msg} — ${UPLOAD_CURL_ERROR}"
            echo "  Attempt ${attempt}/${PUBLISH_RETRIES} failed (${msg}), retrying in ${delay}s..." >&2
            sleep "${delay}"
            delay=$((delay * 2))
        fi
        attempt=$((attempt + 1))
    done

    # All retries exhausted
    return 0
}

# ---------------------------------------------------------------------------
# Upload functions
# ---------------------------------------------------------------------------

upload_maven() {
    if [ -z "${GROUP_ID}" ] || [ -z "${ARTIFACT_ID}" ] || [ -z "${PACKAGING}" ]; then
        echo "ERROR: Maven mode requires group_id, artifact_id, and packaging" >&2
        exit 1
    fi

    local url
    url=$(maven_url)

    local sha256
    sha256=$(compute_sha256 "${FILE_PATH}")

    echo "Uploading artifact to Maven coordinates: ${GROUP_ID}:${ARTIFACT_ID}:${VERSION}"
    echo "  Platform: ${PUBLISH_PLATFORM}"
    echo "  URL: ${url}"
    echo "  File: ${FILE_PATH}"
    [ -n "${sha256}" ] && echo "  SHA-256: ${sha256}"

    if [ -n "${DRY_RUN}" ]; then
        echo "  DRY RUN: would upload ${FILENAME} to ${url}"
        if [ "${PACKAGING}" != "jar" ]; then
            echo "  DRY RUN: would upload POM to $(pom_url)"
        fi
        return
    fi

    local -a checksum_header=()
    if [ -n "${sha256}" ]; then
        checksum_header=(-H "X-Checksum-Sha256: ${sha256}")
    fi

    curl_upload_with_retry \
        -X PUT \
        "${checksum_header[@]}" \
        -T "${FILE_PATH}" \
        "${url}"

    if [ "${UPLOAD_HTTP_CODE}" -ge 200 ] && [ "${UPLOAD_HTTP_CODE}" -lt 300 ]; then
        echo "  Upload successful (HTTP ${UPLOAD_HTTP_CODE})"
    else
        echo "ERROR: Upload failed (HTTP ${UPLOAD_HTTP_CODE})" >&2
        [ -n "${UPLOAD_CURL_ERROR}" ] && echo "  curl: ${UPLOAD_CURL_ERROR}" >&2
        if [ "${UPLOAD_HTTP_CODE}" = "000" ]; then
            echo "  Hint: HTTP 000 means curl could not complete the request." >&2
            echo "  Check ~/.netrc credentials and PUBLISH_URL reachability." >&2
        fi
        exit 1
    fi

    # Upload POM for non-Java artifacts (Java's java_export supplies its own)
    if [ "${PACKAGING}" != "jar" ]; then
        local pom_file
        pom_file=$(generate_pom)
        local pom_upload_url
        pom_upload_url=$(pom_url)
        local pom_sha256
        pom_sha256=$(compute_sha256 "${pom_file}")

        local -a pom_checksum_header=()
        if [ -n "${pom_sha256}" ]; then
            pom_checksum_header=(-H "X-Checksum-Sha256: ${pom_sha256}")
        fi

        echo "  Uploading POM: ${pom_upload_url}"
        curl_upload_with_retry \
            -X PUT \
            "${pom_checksum_header[@]}" \
            -T "${pom_file}" \
            "${pom_upload_url}"

        if [ "${UPLOAD_HTTP_CODE}" -ge 200 ] && [ "${UPLOAD_HTTP_CODE}" -lt 300 ]; then
            echo "  POM upload successful (HTTP ${UPLOAD_HTTP_CODE})"
        else
            echo "WARNING: POM upload failed (HTTP ${UPLOAD_HTTP_CODE})" >&2
            [ -n "${UPLOAD_CURL_ERROR}" ] && echo "  curl: ${UPLOAD_CURL_ERROR}" >&2
        fi

        rm -f "${pom_file}"
    fi
}

prep_pypi() {
    local script_dir
    script_dir="$(dirname "$0")"
    local repackage_script="${script_dir}/repackage_wheel.py"

    if [ ! -f "${repackage_script}" ]; then
        echo "ERROR: repackage_wheel.py not found at ${repackage_script}" >&2
        exit 1
    fi

    _REPACKAGE_TMPDIR=$(mktemp -d)
    local new_wheel
    new_wheel=$(python3 "${repackage_script}" "${FILE_PATH}" "${VERSION}" "${_REPACKAGE_TMPDIR}")

    if [ ! -f "${new_wheel}" ]; then
        echo "ERROR: Wheel repackaging failed — output not found" >&2
        exit 1
    fi

    FILE_PATH="${new_wheel}"
    FILENAME=$(basename "${FILE_PATH}")
    echo "  Repackaged wheel: ${FILENAME}"
}

upload_pypi() {
    echo "Uploading wheel to PyPI repository: ${REPO_NAME}"
    echo "  Platform: ${PUBLISH_PLATFORM}"
    echo "  File: ${FILE_PATH}"

    local pypi_url
    case "${PUBLISH_PLATFORM}" in
        artifactory)
            pypi_url="${PUBLISH_URL}/${REPO_NAME}/"
            ;;
        nexus)
            pypi_url="${PUBLISH_URL}/repository/${REPO_NAME}/"
            ;;
        gitea)
            pypi_url="${PUBLISH_URL}/api/packages/${PUBLISH_OWNER}/pypi"
            ;;
        *)
            echo "ERROR: Unknown platform: ${PUBLISH_PLATFORM}" >&2
            exit 1
            ;;
    esac

    local sha256
    sha256=$(compute_sha256 "${FILE_PATH}")

    echo "  Repository URL: ${pypi_url}"
    [ -n "${sha256}" ] && echo "  SHA-256: ${sha256}"

    if [ -n "${DRY_RUN}" ]; then
        echo "  DRY RUN: would upload ${FILENAME} to ${pypi_url}"
        return
    fi

    curl_upload_with_retry \
        -X POST \
        -F ":action=file_upload" \
        -F "sha256_digest=${sha256}" \
        -F "content=@${FILE_PATH};filename=${FILENAME}" \
        "${pypi_url}"

    if [ "${UPLOAD_HTTP_CODE}" -ge 200 ] && [ "${UPLOAD_HTTP_CODE}" -lt 300 ]; then
        echo "  Upload successful (HTTP ${UPLOAD_HTTP_CODE})"
    else
        echo "ERROR: Upload failed (HTTP ${UPLOAD_HTTP_CODE})" >&2
        [ -n "${UPLOAD_CURL_ERROR}" ] && echo "  curl: ${UPLOAD_CURL_ERROR}" >&2
        if [ "${UPLOAD_HTTP_CODE}" = "000" ]; then
            echo "  Hint: HTTP 000 means curl could not complete the request." >&2
            echo "  Check ~/.netrc credentials and PUBLISH_URL reachability." >&2
        fi
        exit 1
    fi
}

upload_generic() {
    if [ -z "${ARTIFACT_ID}" ]; then
        echo "ERROR: Generic mode requires artifact_id" >&2
        exit 1
    fi

    local url
    url=$(generic_url)

    local sha256
    sha256=$(compute_sha256 "${FILE_PATH}")

    echo "Uploading artifact to generic repository: ${REPO_NAME}"
    echo "  Platform: ${PUBLISH_PLATFORM}"
    echo "  URL: ${url}"
    echo "  File: ${FILE_PATH}"
    [ -n "${sha256}" ] && echo "  SHA-256: ${sha256}"

    if [ -n "${DRY_RUN}" ]; then
        echo "  DRY RUN: would upload ${FILENAME} to ${url}"
        return
    fi

    local -a checksum_header=()
    if [ -n "${sha256}" ]; then
        checksum_header=(-H "X-Checksum-Sha256: ${sha256}")
    fi

    curl_upload_with_retry \
        -X PUT \
        "${checksum_header[@]}" \
        -T "${FILE_PATH}" \
        "${url}"

    if [ "${UPLOAD_HTTP_CODE}" -ge 200 ] && [ "${UPLOAD_HTTP_CODE}" -lt 300 ]; then
        echo "  Upload successful (HTTP ${UPLOAD_HTTP_CODE})"
    else
        echo "ERROR: Upload failed (HTTP ${UPLOAD_HTTP_CODE})" >&2
        [ -n "${UPLOAD_CURL_ERROR}" ] && echo "  curl: ${UPLOAD_CURL_ERROR}" >&2
        if [ "${UPLOAD_HTTP_CODE}" = "000" ]; then
            echo "  Hint: HTTP 000 means curl could not complete the request." >&2
            echo "  Check ~/.netrc credentials and PUBLISH_URL reachability." >&2
        fi
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------
case "${MODE}" in
    maven)
        upload_maven
        ;;
    pypi)
        prep_pypi
        upload_pypi
        ;;
    generic)
        upload_generic
        ;;
    *)
        echo "ERROR: Unknown mode: ${MODE}. Supported modes: maven, pypi, generic" >&2
        exit 1
        ;;
esac
