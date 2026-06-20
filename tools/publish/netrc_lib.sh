# Shared .netrc parsing for the publish credential helpers.
#
# Sourced by tools/publish/credential-helper (Bazel-fetch credential
# helper protocol) and tools/publish/docker-login-helper (writes
# ~/.docker/config.json before image push). Both helpers look up host
# credentials in ~/.netrc with the same logic; this file is the single
# implementation.
#
# This file is sourced — not executed. It must remain plain shell with
# no Bazel-built tool dependencies, since the existing credential-helper
# is invoked by Bazel during fetch (before any Bazel-built tools exist).
#
# Usage:
#   source "$(dirname "${BASH_SOURCE[0]}")/netrc_lib.sh"
#   netrc_lookup "<host>"
#   if [[ -n "${NETRC_LOGIN}" && -n "${NETRC_PASSWORD}" ]]; then
#       # use NETRC_LOGIN and NETRC_PASSWORD
#   fi

# netrc_lookup populates NETRC_LOGIN and NETRC_PASSWORD globals from the
# matching `machine` entry in $NETRC (default: ~/.netrc). Falls back to a
# `default` entry if no machine matches. Sets both empty if the file is
# absent or no entry is found.
netrc_lookup() {
    local host="$1"
    local netrc="${NETRC:-${HOME}/.netrc}"
    NETRC_LOGIN=""
    NETRC_PASSWORD=""

    [[ -f "${netrc}" ]] || return 0

    local in_machine=false
    local line
    while IFS= read -r line || [ -n "$line" ]; do
        line=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        [ -z "$line" ] && continue
        [[ "$line" == \#* ]] && continue

        set -f
        set -- $line
        set +f
        while [ $# -gt 0 ]; do
            case "$1" in
                machine)
                    if [ "${2:-}" = "${host}" ]; then
                        in_machine=true
                    else
                        in_machine=false
                    fi
                    shift 2 || shift 1
                    ;;
                default)
                    if [ -z "${NETRC_LOGIN}" ]; then
                        in_machine=true
                    else
                        in_machine=false
                    fi
                    shift
                    ;;
                login)
                    if [ "${in_machine}" = true ]; then
                        NETRC_LOGIN="${2:-}"
                    fi
                    shift 2 || shift 1
                    ;;
                password)
                    if [ "${in_machine}" = true ]; then
                        NETRC_PASSWORD="${2:-}"
                    fi
                    shift 2 || shift 1
                    ;;
                *)
                    shift
                    ;;
            esac
        done
    done < "${netrc}"
}
