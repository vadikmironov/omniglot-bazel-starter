load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "test_config",
    size = "small",
    srcs = ["test_config.py"],
    deps = ["//tools/publish:mint_lib"],
)

py_test(
    name = "test_version",
    size = "small",
    srcs = ["test_version.py"],
    deps = ["//tools/publish:mint_lib"],
)

py_test(
    name = "test_scope",
    size = "small",
    srcs = ["test_scope.py"],
    deps = ["//tools/publish:mint_lib"],
)

py_test(
    name = "test_label",
    size = "small",
    srcs = ["test_label.py"],
    deps = ["//tools/publish:mint_lib"],
)

py_test(
    name = "test_git",
    size = "small",
    srcs = ["test_git.py"],
    local = True,
    deps = ["//tools/publish:mint_lib"],
)

py_test(
    name = "test_worktree",
    size = "small",
    srcs = ["test_worktree.py"],
    local = True,
    deps = ["//tools/publish:mint_lib"],
)

py_test(
    name = "test_engine",
    size = "small",
    srcs = ["test_engine.py"],
    local = True,
    deps = ["//tools/publish:mint_lib"],
)
