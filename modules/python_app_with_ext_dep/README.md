# Python App with PyPI Dependencies

A `py_binary` that uses the `requests` library from PyPI, demonstrating how to manage external Python dependencies in Bazel. Based on the [rules_python pip integration+docs](https://rules-python.readthedocs.io/en/latest/pypi-dependencies.html).

## Key BUILD Concepts

```bazel
load("@omniglot-bazel-starter_pip_dependencies//:requirements.bzl", "requirement")

py_library(
    name = "python_app_with_ext_dep_lib",
    srcs = glob(["src/**/*.py"], exclude = ["src/**/__main__.py"]),
    imports = ["src"],
    deps = [requirement("requests")],  # PyPI dependency
)
```

The `requirement("requests")` function resolves the package from the pip lockfile. This is generated from `tools/python/requirements.in` which lists all pip dependencies for the repo.

The binary is split from the library so the library can be tested and reused independently:

```bazel
py_binary(
    name = "python_app_with_ext_dep",
    srcs = glob(["src/**/__main__.py"]),
    main = "__main__.py",
    deps = [":python_app_with_ext_dep_lib"],
)
```

## Adding New Dependencies

1. Add the package to `tools/python/requirements.in`
2. Regenerate the lockfile:

```bash
   bazel run //tools/python:generate_requirements_lock.update
```

3. Use `requirement("package-name")` in your BUILD file. For type checking, add type stubs too (e.g., `types-requests` for `requests`).

## Building and Running

```bash
# Build the binary
bazel build //modules/python_app_with_ext_dep:python_app_with_ext_dep

# Run it
bazel run //modules/python_app_with_ext_dep:python_app_with_ext_dep
```
