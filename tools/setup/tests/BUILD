load("@rules_python//python:defs.bzl", "py_test")

# Drives a local HTTP origin that stalls mid-transfer, so it needs real sockets
# and wall-clock timeouts; medium keeps it off the fast unit-test path.
py_test(
    name = "test_download_lib",
    size = "medium",
    srcs = ["test_download_lib.py"],
    data = ["//tools/setup:download_lib.sh"],
    target_compatible_with = select({
        "@platforms//os:windows": ["@platforms//:incompatible"],
        "//conditions:default": [],
    }),
)
