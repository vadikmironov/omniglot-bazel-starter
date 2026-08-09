#!/bin/bash
#
# Resumable downloads for the toolchain installers.
#
#   source download_lib.sh && download_resumable <url> <dest> [curl args...]
#
# Some proxies hand over part of a large response and then go quiet without
# closing the socket: TCP stays ESTABLISHED and curl blocks indefinitely.
# --speed-limit / --speed-time turn that into exit 28 as soon as throughput
# sits under the floor. (--max-time also breaks the hang, but it caps total
# duration rather than idleness, so it cannot tell a hung transfer from a slow
# one and has to be set loose enough for the whole archive.)
#
# Getting curl to retry is the easy half. The hard half is that a retried
# transfer restarts at byte 0 and discards the partial, and --continue-at does
# not change that: the resume offset is resolved once at startup, and the
# internal retries send no Range header at all. That is curl#1084, open since
# 2016 — PRs 15333, 18581 and 18665 all closed unmerged. So the retry loop
# lives here instead, where each attempt is a fresh curl that re-reads the
# bytes already on disk.

# Bytes/sec below which a transfer counts as stalled.
: "${DOWNLOAD_MIN_SPEED:=1024}"
# Seconds under DOWNLOAD_MIN_SPEED before the attempt is aborted.
: "${DOWNLOAD_STALL_SECONDS:=30}"
# Consecutive attempts that fetch nothing new before giving up.
: "${DOWNLOAD_MAX_STALLED_RETRIES:=5}"
# Absolute ceiling, so a trickling origin cannot loop forever.
: "${DOWNLOAD_MAX_ATTEMPTS:=100}"
# Seconds to wait between attempts.
: "${DOWNLOAD_RETRY_DELAY:=2}"
: "${DOWNLOAD_CONNECT_TIMEOUT:=30}"

# Log through the sourcing script's log() when it has one, so installer output
# keeps a single voice.
download_log() {
    if [ "$(type -t log 2>/dev/null)" = "function" ]; then
        log "$@"
    else
        printf '[download] %s\n' "$*" >&2
    fi
}

# Size of $1 in bytes, or 0 when absent. `wc -c` sidesteps the stat -c/-f split
# between GNU and BSD.
download_file_size() {
    if [ -f "$1" ]; then
        wc -c <"$1" | tr -d '[:space:]'
    else
        printf '0'
    fi
}

# download_resumable <url> <dest> [extra curl args...]
#
# Resumes onto an existing partial $dest, so an interrupted run continues where
# it left off. Callers verify a checksum afterwards and must delete $dest when
# it fails — otherwise a poisoned partial would be resumed onto forever.
#
# The retry budget resets whenever an attempt gains bytes, so a proxy that
# releases a fixed slice at a time still finishes; only genuinely stuck
# transfers exhaust it.
download_resumable() {
    local url=$1 dest=$2
    shift 2

    local attempt=0 stalled=0 restarted=0
    local rc before after

    while :; do
        attempt=$((attempt + 1))
        before=$(download_file_size "$dest")

        rc=0
        curl --fail --location --show-error \
            --connect-timeout "$DOWNLOAD_CONNECT_TIMEOUT" \
            --speed-limit "$DOWNLOAD_MIN_SPEED" \
            --speed-time "$DOWNLOAD_STALL_SECONDS" \
            --continue-at - \
            --output "$dest" \
            "$@" \
            "$url" || rc=$?

        # A 416 on an already-complete file exits 0, so this covers "nothing
        # left to fetch" as well as a clean transfer.
        [ "$rc" -eq 0 ] && return 0

        after=$(download_file_size "$dest")

        # 33: origin ignored the Range header. 36: it answered with a range we
        # cannot stitch on. Either way the partial is unusable — drop it and
        # take one clean run from byte 0 before giving up.
        if [ "$rc" -eq 33 ] || [ "$rc" -eq 36 ]; then
            if [ "$restarted" -eq 1 ]; then
                download_log "origin will not serve byte ranges and a restart already failed"
                return "$rc"
            fi
            restarted=1
            rm -f "$dest"
            download_log "origin refused a ranged request; restarting from byte 0"
            continue
        fi

        if [ "$after" -gt "$before" ]; then
            stalled=0
            download_log "stalled after $((after - before)) new bytes (${after} on disk, curl exit ${rc}); resuming"
        else
            stalled=$((stalled + 1))
            download_log "no new bytes (attempt ${stalled}/${DOWNLOAD_MAX_STALLED_RETRIES}, curl exit ${rc})"
        fi

        if [ "$stalled" -ge "$DOWNLOAD_MAX_STALLED_RETRIES" ] ||
            [ "$attempt" -ge "$DOWNLOAD_MAX_ATTEMPTS" ]; then
            download_log "giving up after ${attempt} attempt(s) with ${after} bytes fetched"
            return "$rc"
        fi

        sleep "$DOWNLOAD_RETRY_DELAY"
    done
}
