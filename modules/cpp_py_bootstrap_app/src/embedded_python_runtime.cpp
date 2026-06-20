#define PY_SSIZE_T_CLEAN
#include "embedded_python_runtime.h"

// NOLINTBEGIN(misc-include-cleaner) — Python.h is CPython's umbrella header; sub-headers are internal
#include <Python.h>

#include <memory>
#include <span>
#include <string>
#include <string_view>
#include <utility>
#include <variant>
#include <vector>

#include "gil_release_guard.h"
#include "py_object_guard.h"
#include "py_result_converter.h"
#include "python_lib_resolver.h"
#include "python_toolchain_resolver.h"
#include "spdlog/logger.h"
#include "sub_interpreter_guard.h"

namespace {

/// Returns a new-reference PyObject* (caller owns). nullptr on failure.
auto py_arg_to_object(const PyArg& arg) -> PyObject* {
    return std::visit(
        [](const auto& value) -> PyObject* {
            using T = std::decay_t<decltype(value)>;
            if constexpr (std::is_same_v<T, bool>) {
                return PyBool_FromLong(value ? 1 : 0);
            } else if constexpr (std::is_same_v<T, int>) {
                return PyLong_FromLong(value);
            } else if constexpr (std::is_same_v<T, long long>) {
                return PyLong_FromLongLong(value);
            } else if constexpr (std::is_same_v<T, double>) {
                return PyFloat_FromDouble(value);
            } else if constexpr (std::is_same_v<T, std::string>) {
                return PyUnicode_FromStringAndSize(value.data(), static_cast<Py_ssize_t>(value.size()));
            }
        },
        arg);
}

/// Returns a new-reference tuple from args. nullptr on failure (partial tuple cleaned up).
auto build_args_tuple(std::span<const PyArg> args, spdlog::logger* logger) -> PyObject* {
    PyObject* tuple = PyTuple_New(static_cast<Py_ssize_t>(args.size()));
    if (tuple == nullptr) {
        logger->error("Failed to allocate arguments tuple");
        return nullptr;
    }

    for (Py_ssize_t i = 0; i < static_cast<Py_ssize_t>(args.size()); ++i) {
        PyObject* item = py_arg_to_object(args[static_cast<size_t>(i)]);
        if (item == nullptr) {
            logger->error("Failed to convert argument at index {}", i);
            Py_DECREF(tuple);
            return nullptr;
        }
        // PyTuple_SET_ITEM steals the reference — do NOT wrap item in PyObjectGuard.
        PyTuple_SET_ITEM(tuple, i, item);
    }

    return tuple;
}

}  // namespace

EmbeddedPythonRuntime::EmbeddedPythonRuntime(char** argv, spdlog::logger* logger)
    : argv_(argv), logger_(logger) {}

auto EmbeddedPythonRuntime::create(char** argv, spdlog::logger* logger,
                                   std::string_view toolchain_runfiles_path)
    -> std::unique_ptr<EmbeddedPythonRuntime> {
    // Resolve Python toolchain path
    std::string abs_interpreter_path = std::string();
    std::string const relative_interpreter_path = std::string(toolchain_runfiles_path);
    if (!get_python_toolchain_path_via_runfiles(argv, relative_interpreter_path, abs_interpreter_path)) {
        if (!get_python_toolchain_path_via_env(abs_interpreter_path)) {
            logger->error(
                "Unable to find valid Python toolchain. "
                "Please check PATH or PYTHONHOME if running outside Bazel.");
            return nullptr;
        }
    }

    // Initialize Python interpreter
#if PY_VERSION_HEX >= 0x030E0000
    // Python 3.14+: PEP 741 PyInitConfig API (narrow char* strings, RAII-friendly)
    using unique_py_config_ptr_t = std::unique_ptr<PyInitConfig, decltype(&PyInitConfig_Free)>;

    unique_py_config_ptr_t const py_config = unique_py_config_ptr_t(PyInitConfig_Create(), &PyInitConfig_Free);
    if (not py_config) {
        logger->error("Failed to allocate PyConfig");
        return nullptr;
    }

    if (PyInitConfig_SetStr(py_config.get(), "home", abs_interpreter_path.data()) < 0) {
        const char* err_msg = nullptr;
        (void)PyInitConfig_GetError(py_config.get(), &err_msg);
        logger->error("Failed to set Python home: {}", err_msg != nullptr ? err_msg : "(unknown error)");
        return nullptr;
    }

    if (Py_InitializeFromInitConfig(py_config.get()) < 0) {
        const char* err_msg = nullptr;
        (void)PyInitConfig_GetError(py_config.get(), &err_msg);
        logger->error("Failed to initialize Python interpreter: {}",
                      err_msg != nullptr ? err_msg : "(unknown error)");
        return nullptr;
    }
#else
    // Python < 3.14: PyConfig API (stable since 3.8, uses wchar_t internally)
    PyConfig config;
    PyConfig_InitPythonConfig(&config);

    PyStatus status = PyConfig_SetBytesString(&config, &config.home,
                                              abs_interpreter_path.c_str());
    if (PyStatus_Exception(status)) {
        logger->error("Failed to set Python home: {}",
                      status.err_msg ? status.err_msg : "(unknown error)");
        PyConfig_Clear(&config);
        return nullptr;
    }

    status = Py_InitializeFromConfig(&config);
    if (PyStatus_Exception(status)) {
        logger->error("Failed to initialize Python interpreter: {}",
                      status.err_msg ? status.err_msg : "(unknown error)");
        PyConfig_Clear(&config);
        return nullptr;
    }
    PyConfig_Clear(&config);
#endif

    // Using new directly because the constructor is private (make_unique cannot access it).
    return std::unique_ptr<EmbeddedPythonRuntime>(new EmbeddedPythonRuntime(argv, logger));
}

EmbeddedPythonRuntime::~EmbeddedPythonRuntime() {
    Py_FinalizeEx();
}

auto EmbeddedPythonRuntime::version() const -> std::string_view {
    return Py_GetVersion();
}

void EmbeddedPythonRuntime::add_python_library_path(std::string_view library_relative_path) {
    if (resolved_) {
        logger_->error("Cannot register library path: libraries already resolved");
        return;
    }
    pending_python_library_paths_.emplace_back(library_relative_path);
}

auto EmbeddedPythonRuntime::resolve_python_library_paths() -> bool {
    if (resolved_) {
        logger_->error("Cannot resolve library paths: already resolved");
        return false;
    }

    for (const auto& library_path : pending_python_library_paths_) {
        std::string resolved_path = std::string();
        if (!get_python_lib_path_via_runfiles(argv_, library_path, resolved_path)) {
            if (!get_python_lib_path_via_env(argv_, resolved_path)) {
                logger_->error(
                    "Unable to resolve Python library path: {}. Set PYTHON_LIB_PATH "
                    "environment variable if running outside Bazel.",
                    library_path);
                return false;
            }
        }
        python_library_paths_.push_back(std::move(resolved_path));
    }

    pending_python_library_paths_.clear();
    resolved_ = true;
    return true;
}

auto EmbeddedPythonRuntime::is_resolved() const -> bool {
    return resolved_;
}

auto EmbeddedPythonRuntime::get_python_library_paths() const -> const std::vector<std::string>& {
    return python_library_paths_;
}

auto EmbeddedPythonRuntime::release_gil() const -> GilReleaseGuard {
    return GilReleaseGuard{};
}

auto EmbeddedPythonRuntime::call_in_subinterpreter_impl(
    std::string_view instance_id, std::string_view module_name,
    std::string_view function_name, std::span<const PyArg> args,
    PyResultConverterFn converter, void* out) const -> bool {
    logger_->info("[{}] Starting subinterpreter for {}.{}", instance_id, module_name,
                  function_name);

    // Acquire GIL and create subinterpreter
    PyGILState_STATE const gil_state = PyGILState_Ensure();
    PyThreadState* main_ts = PyThreadState_Get();
    SubInterpreterGuard sub_interp(main_ts, gil_state, logger_);

    if (!sub_interp.create()) {
        return false;
    }

    // Add resolved library paths to sys.path
    if (!python_library_paths_.empty()) {
        PyObjectGuard const sys_module(PyImport_ImportModule("sys"));
        if (!sys_module) {
            logger_->error("Failed to import sys module");
            PyErr_Print();
            return false;
        }

        PyObjectGuard const sys_path(PyObject_GetAttrString(sys_module.get(), "path"));
        if (!sys_path) {
            logger_->error("Failed to get sys.path");
            PyErr_Print();
            return false;
        }

        for (const auto& lib_path_str : python_library_paths_) {
            PyObjectGuard const lib_path(PyUnicode_FromString(lib_path_str.c_str()));
            if (!lib_path) {
                logger_->error("Failed to create path string for: {}", lib_path_str);
                PyErr_Print();
                return false;
            }

            if (PyList_Insert(sys_path.get(), 0, lib_path.get()) != 0) {
                logger_->error("Failed to insert path into sys.path: {}", lib_path_str);
                PyErr_Print();
                return false;
            }
        }
    }

    // Import module and get function
    PyObjectGuard const module(PyImport_ImportModule(std::string(module_name).c_str()));
    if (!module) {
        logger_->error("Failed to import {}", module_name);
        PyErr_Print();
        return false;
    }

    PyObjectGuard const func(PyObject_GetAttrString(module.get(), std::string(function_name).c_str()));
    if (!func || (PyCallable_Check(func.get()) == 0)) {
        logger_->error("Failed to get {} function", function_name);
        PyErr_Print();
        return false;
    }

    // Build arguments tuple and call the function
    PyObjectGuard const py_args(build_args_tuple(args, logger_));
    if (!py_args) {
        return false;
    }

    PyObjectGuard const result(PyObject_CallObject(func.get(), py_args.get()));
    if (!result) {
        logger_->error("Failed to call {}", function_name);
        PyErr_Print();
        return false;
    }

    // Convert result before SubInterpreterGuard destructor runs.
    return converter(logger_, result.get(), out);
}
// NOLINTEND(misc-include-cleaner)
