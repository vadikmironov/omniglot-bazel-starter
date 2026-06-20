# C++ Embedded Python Runtime

A C++ application that embeds a CPython interpreter and calls Python functions from C++ using [subinterpreters](https://docs.python.org/3/c-api/init.html#sub-interpreter-support) with per-interpreter GIL (Python 3.12+). Each subinterpreter runs in complete isolation, enabling true parallel Python execution from multiple C++ threads.

## Architecture

The module has four layers:

1. **Toolchain resolution** — finds a Python installation at runtime, either from Bazel runfiles (hermetic) or from `PYTHONHOME`/`PATH` (local). A [custom Starlark rule](python_interpreter_path_header.bzl) generates a C++ header with the runfiles path at build time; an empty string triggers the environment fallback chain.

2. **Library path resolution** — locates user Python modules (e.g., `//modules/python_lib`) via runfiles or `PYTHON_LIB_PATH` env var, with fallback to conventional install layouts (`../lib/python`, `./python_lib`, `../share/*/python`).

3. **Runtime lifecycle** — `EmbeddedPythonRuntime` manages interpreter initialization and finalization. Factory method `create()` ensures valid state. Supports both [PEP 741](https://peps.python.org/pep-0741/) `PyInitConfig` (Python 3.14+) and legacy `PyConfig` (3.8+) via compile-time `PY_VERSION_HEX` switch.

4. **Subinterpreter calls** — `call_in_subinterpreter<T>()` is the main API. It acquires the GIL, creates an isolated subinterpreter with its own GIL, injects library paths into `sys.path`, imports a module, calls a function with typed arguments, and converts the result back to C++.

### RAII Guards

| Guard | Purpose |
|-------|---------|
| `PyObjectGuard` | Reference-counted `PyObject*` ownership (calls `Py_XDECREF`) |
| `SubInterpreterGuard` | Subinterpreter lifecycle + GIL state restoration |
| `GilReleaseGuard` | Releases GIL on construction, reacquires on destruction |
| `EmbeddedPythonRuntime` | Python interpreter lifecycle (`Py_FinalizeEx`) |

### Supported Argument and Return Types

Arguments (`PyArg` variant): `bool`, `int`, `long long`, `double`, `std::string`

Return types (template specializations): `bool`, `int`, `long long`, `double`, `std::string`. Unsupported types produce a linker error.

## Important: Destruction Order

```cpp
auto runtime = EmbeddedPythonRuntime::create(argv, logger, RULES_PYTHON_RUNFILES_PATH);
auto gil_guard = runtime->release_gil();  // MUST be declared AFTER runtime
// Stack unwinding destroys gil_guard first, restoring GIL before Py_FinalizeEx()
```

The GIL guard must be destroyed before the runtime — `Py_FinalizeEx()` requires the GIL to be held. C++ stack unwinding guarantees this when declared in the correct order.

## Building and Testing

```bash
# Build with hermetic Python toolchain (default)
bazel build //modules/cpp_py_bootstrap_app

# Build with local system Python
bazel build --config=python3_13_host //modules/cpp_py_bootstrap_app

# Run all tests
bazel test //modules/cpp_py_bootstrap_app/...
```

### Test Suites

| Target | What it tests | Needs Python runtime? |
|--------|--------------|----------------------|
| `cpp_py_bootstrap_app_python_toolchain_resolver_test` | Toolchain/lib path resolution using fake filesystem layouts | No |
| `cpp_py_bootstrap_app_python_types_test` | RAII guards, result converters, subinterpreter guard | Yes |
| `cpp_py_bootstrap_app_call_in_subinterpreter_test` | End-to-end: C++ calling real Python functions | Yes + Python libs |

## Toolchain Resolution Fallback Chain

```
1. Bazel runfiles (RULES_PYTHON_RUNFILES_PATH from build-time header)
   ↓ (empty or not found)
2. PYTHONHOME env var (validated: must contain lib/pythonX.Y/os.py)
   ↓ (unset or invalid)
3. PATH search for python3/python (symlinks resolved, stdlib validated)
```

The stdlib validation is version-agnostic — it scans `<home>/lib/` for any `python*/os.py` directory rather than requiring a specific version.
