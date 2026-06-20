#!/usr/bin/env bash
#
# Install the Bazelisk launcher. Bazelisk downloads and runs the Bazel version
# pinned in .bazelversion, so it is the only Bazel binary a contributor needs.
# Run with --help for modes and options.

set -euo pipefail

readonly USER_BIN_DIR="${HOME}/.local/bin"
readonly PATH_MARKER="# added by install_bazelisk.sh"
readonly RELEASES="https://github.com/bazelbuild/bazelisk/releases"
readonly API="https://api.github.com/repos/bazelbuild/bazelisk/releases/latest"

# Logs go to stderr so functions can return values on stdout via $(...).
log() { printf '[bazelisk-install] %s\n' "$*" >&2; }
die() {
  printf '[bazelisk-install] ERROR: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
install_bazelisk.sh — install the Bazelisk launcher.

Modes:
  system   apt/.deb install (lands in /usr/bin); needs root or sudo.
  user     no-sudo install of the raw binary to ~/.local/bin, adding a
           PATH entry to your shell startup file (only if not already there).

With no flag the mode is auto-detected: system when running as root or when
passwordless sudo is available, otherwise user. Auto-detect never triggers an
interactive sudo password prompt — pass --system explicitly for that.

Usage:
  install_bazelisk.sh [--system | --user] [--help]

Environment:
  BAZELISK_VERSION   Pin a release tag (e.g. v1.25.0) instead of querying
                     GitHub for the latest.
EOF
}

# --- argument parsing --------------------------------------------------------

MODE=auto
while [[ $# -gt 0 ]]; do
  case "$1" in
    --system) MODE=system ;;
    --user) MODE=user ;;
    -h | --help)
      usage
      exit 0
      ;;
    *) die "unknown argument: $1 (try --help)" ;;
  esac
  shift
done

# --- platform detection ------------------------------------------------------

[[ "$(uname -s)" == "Linux" ]] || die "this installer supports Linux only (found $(uname -s))"

detect_arch() {
  local machine
  machine=$(uname -m)
  case "$machine" in
    x86_64 | amd64) echo amd64 ;;
    aarch64 | arm64) echo arm64 ;;
    *) die "unsupported architecture: ${machine}" ;;
  esac
}

# Root, or sudo that won't prompt for a password (cached session / NOPASSWD).
have_privileges() {
  [[ ${EUID} -eq 0 ]] && return 0
  command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null
}

resolve_mode() {
  [[ "$MODE" != auto ]] && return 0
  if command -v apt-get >/dev/null 2>&1 && have_privileges; then
    MODE=system
    log "Auto-detected mode: system (apt-get + privileges available)"
  else
    MODE=user
    log "Auto-detected mode: user (no passwordless privileges; using ${USER_BIN_DIR})"
  fi
}

# --- release resolution ------------------------------------------------------

resolve_version() {
  if [[ -n "${BAZELISK_VERSION:-}" ]]; then
    echo "${BAZELISK_VERSION}"
    return 0
  fi
  log "Fetching latest release tag from GitHub..."
  local tag
  tag=$(curl -fsSL "${API}" | grep -Po '"tag_name": "\K[^"]+' || true)
  [[ -n "$tag" ]] || die "could not determine latest version (GitHub API rate limit?); set BAZELISK_VERSION to pin one"
  echo "$tag"
}

# Download an asset and its .sha256 sidecar into WORKDIR, verify, echo the path.
fetch_and_verify() {
  local asset=$1
  local base="${RELEASES}/download/${VERSION}"
  log "Downloading ${asset}..."
  curl -fsSL -o "${WORKDIR}/${asset}" "${base}/${asset}"
  curl -fsSL -o "${WORKDIR}/${asset}.sha256" "${base}/${asset}.sha256"

  local expected actual
  expected=$(awk '{print $1}' "${WORKDIR}/${asset}.sha256")
  actual=$(sha256sum "${WORKDIR}/${asset}" | awk '{print $1}')
  [[ "$expected" == "$actual" ]] ||
    die "SHA256 mismatch for ${asset} (expected ${expected}, got ${actual})"
  log "✓ SHA256 verified for ${asset}"

  printf '%s\n' "${WORKDIR}/${asset}"
}

# --- PATH wiring (user mode) -------------------------------------------------

shell_rc_file() {
  case "$(basename "${SHELL:-bash}")" in
    bash) echo "${HOME}/.bashrc" ;;
    zsh) echo "${ZDOTDIR:-$HOME}/.zshrc" ;;
    fish) echo "${HOME}/.config/fish/config.fish" ;;
    *) echo "" ;;
  esac
}

add_to_path() {
  local dir=$1 rc

  # Already reachable in this environment — e.g. another installer or the
  # distro's ~/.profile already puts ~/.local/bin on PATH. Nothing to wire up.
  case ":${PATH}:" in
    *":${dir}:"*)
      log "${dir} is already on PATH; no shell startup change needed"
      return 0
      ;;
  esac

  rc=$(shell_rc_file)
  if [[ -z "$rc" ]]; then
    log "Could not determine your shell startup file (SHELL=${SHELL:-unset})."
    log "Add this line to it manually: export PATH=\"${dir}:\$PATH\""
    return 0
  fi

  # Already referenced in the startup file (by us on a prior run, or by another
  # tool) but not yet active in this shell — don't duplicate, just prompt to
  # reload. Match the home-relative tail (e.g. .local/bin) so every spelling is
  # recognised: ~/, $HOME/, ${HOME}/, /home/<user>/ and /home/$USER/ forms.
  local needle="${dir#"${HOME}"/}"
  if [[ -f "$rc" ]] && grep -qF -- "$needle" "$rc"; then
    log "${dir} already referenced in ${rc}; restart your shell (or: source ${rc})"
    return 0
  fi

  mkdir -p "$(dirname "$rc")"
  if [[ "$rc" == *config.fish ]]; then
    printf '\n%s\nfish_add_path %s\n' "$PATH_MARKER" "$dir" >>"$rc"
  else
    printf '\n%s\nexport PATH="%s:$PATH"\n' "$PATH_MARKER" "$dir" >>"$rc"
  fi
  log "Added ${dir} to PATH in ${rc}; restart your shell (or: source ${rc})"
}

# --- installers --------------------------------------------------------------

install_system() {
  command -v apt-get >/dev/null 2>&1 || die "--system requires apt-get (Debian/Ubuntu)"
  local deb sudo=""
  deb=$(fetch_and_verify "bazelisk-$(detect_arch).deb")
  [[ ${EUID} -eq 0 ]] || sudo=sudo
  log "Installing via apt-get..."
  ${sudo} apt-get install -y "$deb"
}

install_user() {
  local binary
  binary=$(fetch_and_verify "bazelisk-linux-$(detect_arch)")
  mkdir -p "$USER_BIN_DIR"
  install -m 0755 "$binary" "${USER_BIN_DIR}/bazelisk"
  ln -sf bazelisk "${USER_BIN_DIR}/bazel"
  log "Installed bazelisk and bazel -> bazelisk in ${USER_BIN_DIR}"
  add_to_path "$USER_BIN_DIR"
}

# --- main --------------------------------------------------------------------

resolve_mode

WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT

VERSION=$(resolve_version)
log "Target version: ${VERSION}"

case "$MODE" in
  system) install_system ;;
  user) install_user ;;
  *) die "internal: unresolved mode '${MODE}'" ;;
esac

log "✓ Bazelisk ${VERSION} installed (${MODE} mode). Verify with: bazel version"
