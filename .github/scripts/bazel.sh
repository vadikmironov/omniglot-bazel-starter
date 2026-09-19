#!/usr/bin/env bash
# Run a Bazel command with the BuildBuddy remote cache when a key is present,
# and once more without it when the failure was the cache, not the build.
#
#   bazel.sh <command> [args...]        e.g. bazel.sh test //...
#
# Environment:
#   BUILDBUDDY_API_KEY   empty (fork PRs get no secrets) = never use the cache
#   BAZEL_CACHE_CONFIG   config that turns the cache on; default remote-cache
#   BAZEL_STARTUP_OPTS   startup options, e.g. --output_base=C:/bazel_build
#
# No Bazel 9 flag keeps a build going when the cache cannot be reached:
# --remote_local_fallback and the circuit breaker both still exit 34. So the
# retry lives here, keyed on the exit codes Bazel reserves for remote and
# build-event failures. A build or test failure (1, 3) is never retried.
# https://github.com/bazelbuild/bazel/blob/9.2.0/src/main/java/com/google/devtools/build/lib/util/ExitCode.java
set -uo pipefail

command="$1"
shift
read -r -a startup <<<"${BAZEL_STARTUP_OPTS:-}"

# ${a[@]+...}: bash 3.2 (still /bin/bash on macOS) treats an empty array as unset.
run_bazel() {
  bazel ${startup[@]+"${startup[@]}"} "$@"
}

if [ -z "${BUILDBUDDY_API_KEY:-}" ]; then
  echo "Remote cache disabled (no API key available)"
  run_bazel "$command" "$@"
  exit $?
fi

echo "Remote cache enabled"
# The cache flags go straight after the command: `bazel run` hands anything
# after the target to the program it runs.
run_bazel "$command" \
  --config="${BAZEL_CACHE_CONFIG:-remote-cache}" \
  --remote_header=x-buildbuddy-api-key="$BUILDBUDDY_API_KEY" \
  "$@"
status=$?

case "$status" in
  32 | 34 | 38 | 39 | 45) ;;
  *) exit "$status" ;;
esac

echo "::warning title=Remote cache unavailable::bazel $command exited $status, a remote cache or build event failure. Retrying once without the remote cache."
run_bazel "$command" "$@"
