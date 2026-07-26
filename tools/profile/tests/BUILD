load("@rules_python//python:defs.bzl", "py_test")

# =========================================================================
# Spine tests — driven against the real pb2folded/inferno binaries over
# captured profiles in testdata/, one per pprof heap shape the repo emits.
# =========================================================================

py_test(
    name = "test_spine",
    size = "small",
    srcs = ["test_spine.py"],
    data = glob(["testdata/*.pb"]) + [
        "//tools/profile/pb2folded",
        "@crates//:inferno__inferno-collapse-perf",
        "@crates//:inferno__inferno-flamegraph",
    ],
    env = {
        "PROFILE_COLLAPSE_PERF": "$(rlocationpath @crates//:inferno__inferno-collapse-perf)",
        "PROFILE_INFERNO": "$(rlocationpath @crates//:inferno__inferno-flamegraph)",
        "PROFILE_PB2FOLDED": "$(rlocationpath //tools/profile/pb2folded)",
    },
    deps = ["//tools/profile:profiling_lib"],
)
