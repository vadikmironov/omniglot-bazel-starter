# Python C Extension Module

A [Python extension module](https://docs.python.org/3/extending/extending.html) written in C++, demonstrating how to build native Python modules with Bazel using `cc_binary` with `linkshared=True` and `py_library`. The module wraps functions from `cpp_library` and exposes them to Python.

This example is using the rules_python facilities added under [this C extensions support request](https://github.com/bazel-contrib/rules_python/issues/824).

## Architecture

The module uses a two-layer structure to avoid naming conflicts and enable proper type checking:

- **`cpp_py_ext_module_impl`** - The C++ extension module (`.so`/`.pyd`)
- **`cpp_py_ext_module`** - Python package that imports and re-exports from the impl module
- **`cpp_py_ext_module_impl.pyi`** - Type stubs for mypy support

This separation allows mypy to properly type-check code that imports the extension.

## Key BUILD Concepts

Building a Python C extension requires:

1. **cc_binary with linkshared=True** - Builds the native extension as `cpp_py_ext_module_impl`
2. **genrule + alias** - Provides platform-correct extension (`.pyd` on Windows, `.so` elsewhere)
3. **py_library with imports** - Makes the extension importable from Python
4. **Type stubs (.pyi)** - Provides type information for mypy

### Platform Notes

- **Windows**: Must link `@rules_python//python/cc:current_py_cc_libs` and use `.pyd` extension
- **macOS**: Uses `-undefined dynamic_lookup` for runtime symbol resolution
- **Linux**: Standard `.so` extension works directly

See the [BUILD](BUILD) file for the complete implementation.

## Module State and Multi-Phase Initialization

The extension uses [multi-phase initialization (PEP 489)](https://peps.python.org/pep-0489/) with per-module state for sub-interpreter and [free-threaded Python](https://py-free-threading.github.io/porting-extensions/) compatibility.

## Building and Testing

```bash
# Build the extension module
bazel build //modules/cpp_py_ext_module:cpp_py_ext_module_impl

# Build and run the example binary
bazel run //modules/cpp_py_ext_module

# Run tests
bazel test //modules/cpp_py_ext_module:cpp_py_ext_module_test
```
