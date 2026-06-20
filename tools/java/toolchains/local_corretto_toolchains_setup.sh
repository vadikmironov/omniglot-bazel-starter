#!/bin/bash

set -euo pipefail

# Requires bash 4.0+ for associative arrays and nameref variables
# macOS ships with bash 3.2 by default; install bash 4+ via: brew install bash
if ((BASH_VERSINFO[0] < 4)); then
    echo "ERROR: This script requires bash 4.0 or later (found: $BASH_VERSION)" >&2
    echo "macOS users: install via 'brew install bash' then run with /opt/homebrew/bin/bash or /usr/local/bin/bash" >&2
    exit 1
fi

SCRIPT_NAME=$(basename "$0")

usage() {
    echo "Usage: $SCRIPT_NAME --toolchain_root_path PATH | -r PATH"
    echo "  --toolchain_root_path, -r PATH: Directory where JDK toolchains will be downloaded and extracted"
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

log "Creating toolchain root directory: $TOOLCHAIN_ROOT_PATH"
mkdir -p "$TOOLCHAIN_ROOT_PATH" || error "Failed to create directory: $TOOLCHAIN_ROOT_PATH"
cd "$TOOLCHAIN_ROOT_PATH" || error "Failed to change to directory: $TOOLCHAIN_ROOT_PATH"

detect_platform() {
    local os=$(uname -s | tr '[:upper:]' '[:lower:]')
    local arch=$(uname -m)

    case "$os" in
        linux*)
            case "$arch" in
                x86_64) echo "linux-x64" ;;
                aarch64) echo "linux-aarch64" ;;
                i386|i686) echo "linux-x86" ;;
                armv7l|armv6l) echo "linux-aarch32" ;;
                *) error "Unsupported Linux architecture: $arch" ;;
            esac
            ;;
        darwin*)
            case "$arch" in
                x86_64) echo "macos-x64" ;;
                arm64) echo "macos-aarch64" ;;
                *) error "Unsupported macOS architecture: $arch" ;;
            esac
            ;;
        mingw*|cygwin*|msys*)
            case "$arch" in
                x86_64) echo "windows-x64" ;;
                i386|i686) echo "windows-x86" ;;
                *) error "Unsupported Windows architecture: $arch" ;;
            esac
            ;;
        *)
            error "Unsupported operating system: $os"
            ;;
    esac
}

PLATFORM=$(detect_platform)
log "Detected platform: $PLATFORM"

declare -A JAVA8_URLS=(
    ["linux-x64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-8-x64-linux-jdk.tar.gz"
    ["linux-x64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-8-x64-linux-jdk.tar.gz"
    ["linux-aarch64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-8-aarch64-linux-jdk.tar.gz"
    ["linux-aarch64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-8-aarch64-linux-jdk.tar.gz"
    ["linux-x86-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-8-x86-linux-jdk.tar.gz"
    ["linux-x86-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-8-x86-linux-jdk.tar.gz"
    ["linux-aarch32-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-8-aarch32-linux-jdk.tar.gz"
    ["linux-aarch32-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-8-aarch32-linux-jdk.tar.gz"
    ["windows-x64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-8-x64-windows-jdk.zip"
    ["windows-x64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-8-x64-windows-jdk.zip"
    ["windows-x86-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-8-x86-windows-jdk.zip"
    ["windows-x86-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-8-x86-windows-jdk.zip"
    ["macos-x64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-8-x64-macos-jdk.tar.gz"
    ["macos-x64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-8-x64-macos-jdk.tar.gz"
    ["macos-aarch64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-8-aarch64-macos-jdk.tar.gz"
    ["macos-aarch64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-8-aarch64-macos-jdk.tar.gz"
)

declare -A JAVA11_URLS=(
    ["linux-x64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-11-x64-linux-jdk.tar.gz"
    ["linux-x64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-11-x64-linux-jdk.tar.gz"
    ["linux-aarch64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-11-aarch64-linux-jdk.tar.gz"
    ["linux-aarch64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-11-aarch64-linux-jdk.tar.gz"
    ["linux-x86-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-11-x86-linux-jdk.tar.gz"
    ["linux-x86-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-11-x86-linux-jdk.tar.gz"
    ["linux-aarch32-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-11-aarch32-linux-jdk.tar.gz"
    ["linux-aarch32-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-11-aarch32-linux-jdk.tar.gz"
    ["windows-x64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-11-x64-windows-jdk.zip"
    ["windows-x64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-11-x64-windows-jdk.zip"
    ["windows-x86-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-11-x86-windows-jdk.zip"
    ["windows-x86-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-11-x86-windows-jdk.zip"
    ["macos-x64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-11-x64-macos-jdk.tar.gz"
    ["macos-x64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-11-x64-macos-jdk.tar.gz"
    ["macos-aarch64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-11-aarch64-macos-jdk.tar.gz"
    ["macos-aarch64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-11-aarch64-macos-jdk.tar.gz"
)

declare -A JAVA17_URLS=(
    ["linux-x64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-17-x64-linux-jdk.tar.gz"
    ["linux-x64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-17-x64-linux-jdk.tar.gz"
    ["linux-aarch64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-17-aarch64-linux-jdk.tar.gz"
    ["linux-aarch64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-17-aarch64-linux-jdk.tar.gz"
    ["linux-x86-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-17-x86-linux-jdk.tar.gz"
    ["linux-x86-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-17-x86-linux-jdk.tar.gz"
    ["linux-aarch32-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-17-aarch32-linux-jdk.tar.gz"
    ["linux-aarch32-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-17-aarch32-linux-jdk.tar.gz"
    ["windows-x64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-17-x64-windows-jdk.zip"
    ["windows-x64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-17-x64-windows-jdk.zip"
    ["macos-x64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-17-x64-macos-jdk.tar.gz"
    ["macos-x64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-17-x64-macos-jdk.tar.gz"
    ["macos-aarch64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-17-aarch64-macos-jdk.tar.gz"
    ["macos-aarch64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-17-aarch64-macos-jdk.tar.gz"
)

declare -A JAVA21_URLS=(
    ["linux-x64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-21-x64-linux-jdk.tar.gz"
    ["linux-x64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-21-x64-linux-jdk.tar.gz"
    ["linux-aarch64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-21-aarch64-linux-jdk.tar.gz"
    ["linux-aarch64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-21-aarch64-linux-jdk.tar.gz"
    ["linux-x86-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-21-x86-linux-jdk.tar.gz"
    ["linux-x86-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-21-x86-linux-jdk.tar.gz"
    ["linux-aarch32-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-21-aarch32-linux-jdk.tar.gz"
    ["linux-aarch32-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-21-aarch32-linux-jdk.tar.gz"
    ["windows-x64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-21-x64-windows-jdk.zip"
    ["windows-x64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-21-x64-windows-jdk.zip"
    ["macos-x64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-21-x64-macos-jdk.tar.gz"
    ["macos-x64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-21-x64-macos-jdk.tar.gz"
    ["macos-aarch64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-21-aarch64-macos-jdk.tar.gz"
    ["macos-aarch64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-21-aarch64-macos-jdk.tar.gz"
)

declare -A JAVA25_URLS=(
    ["linux-x64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-25-x64-linux-jdk.tar.gz"
    ["linux-x64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-25-x64-linux-jdk.tar.gz"
    ["linux-aarch64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-25-aarch64-linux-jdk.tar.gz"
    ["linux-aarch64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-25-aarch64-linux-jdk.tar.gz"
    ["linux-x86-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-25-x86-linux-jdk.tar.gz"
    ["linux-x86-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-25-x86-linux-jdk.tar.gz"
    ["linux-aarch32-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-25-aarch32-linux-jdk.tar.gz"
    ["linux-aarch32-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-25-aarch32-linux-jdk.tar.gz"
    ["windows-x64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-25-x64-windows-jdk.zip"
    ["windows-x64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-25-x64-windows-jdk.zip"
    ["macos-x64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-25-x64-macos-jdk.tar.gz"
    ["macos-x64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-25-x64-macos-jdk.tar.gz"
    ["macos-aarch64-archive"]="https://corretto.aws/downloads/latest/amazon-corretto-25-aarch64-macos-jdk.tar.gz"
    ["macos-aarch64-checksum"]="https://corretto.aws/downloads/latest_checksum/amazon-corretto-25-aarch64-macos-jdk.tar.gz"
)

download_jdk() {
    local archive_url="$1"
    local checksum_url="$2"
    local filename=$(basename "$archive_url")
    local checksum_file="${filename}.md5"

    log "Downloading $filename from $archive_url"
    if ! curl -L -f --progress-bar -o "$filename" "$archive_url"; then
        error "Failed to download $filename"
    fi

    log "Downloading checksum file $checksum_file from $checksum_url"
    if ! curl -L -f -s -o "$checksum_file" "$checksum_url" 2>/dev/null; then
        error "Failed to download checksum file $checksum_file"
    fi
}

validate_checksum() {
    local filename="$1"
    local checksum_file="$2"

    log "Validating checksum for $filename"
    if command -v md5sum >/dev/null 2>&1; then
        if ! echo "$(cat "$checksum_file") $filename" | md5sum -c -; then
            error "Checksum validation failed for $filename"
        fi
    elif command -v md5 >/dev/null 2>&1; then
        local expected_checksum=$(cat "$checksum_file")
        local actual_checksum=$(md5 -q "$filename")
        if [ "$expected_checksum" != "$actual_checksum" ]; then
            error "Checksum validation failed for $filename (expected: $expected_checksum, got: $actual_checksum)"
        fi
        log "Checksum validation passed for $filename"
    else
        log "Warning: No MD5 utility found, skipping checksum validation"
    fi
}

extract_jdk() {
    local filename="$1"
    local version="$2"

    log "Extracting $filename"
    case "$filename" in
        *.tar.gz)
            if ! tar -xzf "$filename"; then
                error "Failed to extract $filename"
            fi
            ;;
        *.zip)
            if ! unzip -q "$filename"; then
                error "Failed to extract $filename"
            fi
            ;;
        *)
            error "Unsupported archive format: $filename"
            ;;
    esac

    # Find extracted directory matching the specific version being installed
    # Pattern: amazon-corretto-{version}.{minor}.{patch}-{os}-{platform}
    local extracted_dir_path=$(find . -maxdepth 1 -type d -name "amazon-corretto-${version}.*" -newer "$filename" 2>/dev/null | head -n1)
    if [ -z "$extracted_dir_path" ]; then
        # Fallback: find the most recently created directory matching the version
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # Use stat for macOS compatibility (GNU find -printf not available on macOS)
            extracted_dir_path=$(find . -maxdepth 1 -type d -name "amazon-corretto-${version}.*" -exec stat -f '%m %N' {} \; 2>/dev/null | sort -nr | head -n1 | cut -d' ' -f2-)
        else
            # Linux: use GNU find -printf
            extracted_dir_path=$(find . -maxdepth 1 -type d -name "amazon-corretto-${version}.*" -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n1 | cut -d' ' -f2)
        fi
    fi

    if [ -n "$extracted_dir_path" ]; then
        extracted_dir=$(basename "$extracted_dir_path")
        log "Found extracted directory: $extracted_dir"
    else
        error "Could not find extracted directory for version $version"
    fi
}

create_symlink() {
    local version="$1"
    local extracted_dir="$2"
    local symlink_name="amazon_corretto_jdk_${version}_latest"

    # If symlink exists, check if it already points to the correct directory
    if [ -L "$symlink_name" ]; then
        local old_target=$(readlink "$symlink_name")
        if [ "$old_target" = "$extracted_dir" ]; then
            log "Symlink already points to current directory: $extracted_dir - no action needed"
            return 0
        elif [ -d "$old_target" ]; then
            log "Removing previous JDK installation: $old_target"
            rm -rf "$old_target"
        fi
        rm -f "$symlink_name"
    elif [ -e "$symlink_name" ]; then
        rm -rf "$symlink_name"
    fi

    # Create new symlink
    ln -sf "$extracted_dir" "$symlink_name"
    log "Created symlink: $symlink_name -> $extracted_dir"
}

cleanup_files() {
    local filename="$1"
    local checksum_file="$2"

    log "Cleaning up downloaded files"
    rm -f "$filename" "$checksum_file" || log "Warning: Failed to clean up some files"
}

download_and_install_jdk() {
    local version="$1"
    local urls_var="$2"
    local -n urls=$urls_var

    local archive_key="${PLATFORM}-archive"
    local checksum_key="${PLATFORM}-checksum"

    if [[ -z "${urls[$archive_key]:-}" ]]; then
        log "Skipping Java $version - no archive URL for platform $PLATFORM"
        return 0
    fi

    local archive_url="${urls[$archive_key]}"
    local checksum_url="${urls[$checksum_key]}"
    local filename=$(basename "$archive_url")
    local checksum_file="${filename}.md5"

    log "Processing Java $version for $PLATFORM"

    # Download
    download_jdk "$archive_url" "$checksum_url"

    # Validate
    validate_checksum "$filename" "$checksum_file"

    # Extract
    local extracted_dir=""
    extract_jdk "$filename" "$version" # extract_jdk stores result into extracted_dir

    # Create symlink
    create_symlink "$version" "$extracted_dir"

    # Cleanup
    cleanup_files "$filename" "$checksum_file"

    log "Successfully installed Java $version"
}

declare -A VERSIONS=(
    ["8"]="JAVA8_URLS"
    ["11"]="JAVA11_URLS"
    ["17"]="JAVA17_URLS"
    ["21"]="JAVA21_URLS"
    ["25"]="JAVA25_URLS"
)

log "Starting JDK installation process"
for version in 8 11 17 21 25; do
    download_and_install_jdk "$version" "${VERSIONS[$version]}"
done

log "All JDK versions processed successfully"
log "Installation directory: $TOOLCHAIN_ROOT_PATH"
log "Available JDK installations:"
find "$TOOLCHAIN_ROOT_PATH" -maxdepth 1 -type d -name "amazon-corretto-*" | sort || log "Warning: Failed to list installations"
