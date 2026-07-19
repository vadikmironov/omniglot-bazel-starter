#!/bin/bash

set -euo pipefail

# Downloads and installs a Go SDK for the host Go toolchain, mirroring
# tools/java/toolchains/local_corretto_toolchains_setup.sh for Corretto JDKs.
#
# By default the latest stable release (per https://go.dev/VERSION?m=text) is
# installed to <toolchain_root_path>/go<version>; versioned directories let
# several SDKs coexist, and host_go_discovery.bzl picks the newest. Archives
# are fetched from dl.google.com with SHA256 verification against the
# published .sha256 file. Useful when https://go.dev/dl is not reachable from
# the build (e.g. behind an Artifactory caching proxy) and the hermetic
# rules_go download cannot be used.

SCRIPT_NAME=$(basename "$0")

usage() {
    echo "Usage: $SCRIPT_NAME --toolchain_root_path PATH | -r PATH [--version goX.Y.Z]"
    echo "  --toolchain_root_path, -r PATH: Directory where Go SDKs will be downloaded and extracted"
    echo "  --version goX.Y.Z: Go version to install (default: latest stable from go.dev)"
    exit 1
}

log() {
    printf "[%s] %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
    sync
}

error() {
    printf "[%s] ERROR: %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >&2
    sync
    exit 1
}

TOOLCHAIN_ROOT_PATH=""
GO_VERSION=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --toolchain_root_path)
            TOOLCHAIN_ROOT_PATH="$2"
            shift 2
            ;;
        -r)
            TOOLCHAIN_ROOT_PATH="$2"
            shift 2
            ;;
        --version)
            GO_VERSION="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            error "Unknown option: $1"
            ;;
    esac
done

if [ -z "$TOOLCHAIN_ROOT_PATH" ]; then
    error "toolchain_root_path argument is required, call with --help for usage"
fi

detect_platform() {
    local os
    local arch
    os=$(uname -s | tr '[:upper:]' '[:lower:]')
    arch=$(uname -m)

    case "$os" in
        linux*)
            case "$arch" in
                x86_64) echo "linux-amd64" ;;
                aarch64) echo "linux-arm64" ;;
                *) error "Unsupported Linux architecture: $arch" ;;
            esac
            ;;
        darwin*)
            case "$arch" in
                x86_64) echo "darwin-amd64" ;;
                arm64) echo "darwin-arm64" ;;
                *) error "Unsupported macOS architecture: $arch" ;;
            esac
            ;;
        *)
            error "Unsupported operating system: $os"
            ;;
    esac
}

PLATFORM=$(detect_platform)
log "Detected platform: $PLATFORM"

if [ -z "$GO_VERSION" ]; then
    log "Resolving latest stable Go version from go.dev"
    GO_VERSION=$(curl -fsSL "https://go.dev/VERSION?m=text" | head -1)
    [ -n "$GO_VERSION" ] || error "Failed to resolve latest Go version"
fi
case "$GO_VERSION" in
    go*) ;;
    *) GO_VERSION="go$GO_VERSION" ;;
esac
log "Installing Go version: $GO_VERSION"

DEST="$TOOLCHAIN_ROOT_PATH/$GO_VERSION"
if [ -x "$DEST/bin/go" ]; then
    log "Already installed at $DEST, nothing to do"
    exit 0
fi

mkdir -p "$TOOLCHAIN_ROOT_PATH" || error "Failed to create directory: $TOOLCHAIN_ROOT_PATH"

ARCHIVE="$GO_VERSION.$PLATFORM.tar.gz"
BASE_URL="https://dl.google.com/go"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

log "Downloading $BASE_URL/$ARCHIVE"
curl -fSL -o "$TMP_DIR/$ARCHIVE" "$BASE_URL/$ARCHIVE" || error "Download failed: $ARCHIVE"

log "Verifying SHA256 checksum"
EXPECTED_SHA=$(curl -fsSL "$BASE_URL/$ARCHIVE.sha256") || error "Failed to fetch checksum for $ARCHIVE"
echo "$EXPECTED_SHA  $TMP_DIR/$ARCHIVE" | sha256sum -c - >/dev/null || error "Checksum mismatch for $ARCHIVE"

log "Extracting to $DEST"
tar -xzf "$TMP_DIR/$ARCHIVE" -C "$TMP_DIR" || error "Extraction failed"
[ -d "$TMP_DIR/go" ] || error "Archive did not contain the expected top-level 'go' directory"
mv "$TMP_DIR/go" "$DEST" || error "Failed to move SDK into place"

log "Installed: $DEST ($("$DEST/bin/go" version))"
log "Select it with: bazel build --config=go_host <target>"
