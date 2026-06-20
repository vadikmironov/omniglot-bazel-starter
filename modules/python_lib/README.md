# Python Library Example

A minimal `py_library` with unit tests, showing how to structure Python code in a Bazel monorepo. This follows the same `src/tests` layout as [Doug Thor's bazel-python example](https://github.com/dougthor42/bazel-python-src-tests-example/tree/master).

## Key BUILD Concepts

```bazel
py_library(
    name = "python_lib",
    srcs = glob(["src/**/*.py"]),
    imports = ["src"],  # Makes "import python_lib" work
)
```

The `imports = ["src"]` attribute adds `src/` to the Python path, so other code can write `import python_lib` instead of `import src.python_lib`. This matches how the library would be imported if installed via pip.

```bazel
py_test(
    name = "test_hello_world_lib",
    timeout = "short",
    srcs = glob(["tests/test_hello_world_function/**/*.py"]),
    deps = ["//modules/python_lib"],
)
```

Tests depend on the library target and use standard `unittest`. The `timeout = "short"` tells Bazel to fail fast if the test hangs.

## Building and Testing

```bash
# Build the library
bazel build //modules/python_lib

# Run tests
bazel test //modules/python_lib:test_hello_world_lib

# Run all Python tests in the repo
bazel test //modules/python_lib/...
```

## Using This Library From Other Targets

Other Bazel targets can depend on this library:

```bazel
py_binary(
    name = "my_app",
    srcs = ["main.py"],
    deps = ["//modules/python_lib"],
)
```

Then in Python:
```bazel
from python_lib import get_hello_world_string
```
