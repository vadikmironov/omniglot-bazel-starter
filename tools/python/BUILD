load("@rules_python//python/uv:lock.bzl", "lock")
load(":venv.bzl", "create_venv")

# Resolves pyproject.toml (every dependency group, every platform) into uv.lock.
# `bazel run //tools/python:lock.update` refreshes the source-tree copy;
# `bazel run //tools/python:lock.run -- --upgrade` also upgrades existing pins.
lock(
    name = "lock",
    srcs = ["pyproject.toml"],
    out = "uv.lock",
)

# Creates ./.venv from uv.lock with the hermetic interpreter so pre-commit and
# editor tooling (ruff, ty) run without a Bazel round trip.
create_venv(
    name = "generate_virtual_env",
    lock = "uv.lock",
    pyproject = "pyproject.toml",
)
