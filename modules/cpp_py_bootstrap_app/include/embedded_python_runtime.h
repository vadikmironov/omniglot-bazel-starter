#pragma once

#define PY_SSIZE_T_CLEAN
// NOLINTNEXTLINE(misc-include-cleaner)
#include <Python.h>

#include <initializer_list>
#include <memory>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

#include "gil_release_guard.h"
#include "py_arg.h"
#include "py_result_converter.h"
#include "spdlog/logger.h"

/// RAII wrapper managing the lifecycle of an embedded Python runtime.
///
/// Created exclusively via create(). If you have an instance, the interpreter
/// is fully initialized. Non-copyable, non-movable (Python runtime is process-global).
class EmbeddedPythonRuntime {
public:
    /// Creates a fully initialized runtime, or nullptr on failure (errors are logged).
    ///
    /// @param argv Program arguments (argv[0] used for runfiles resolution).
    /// @param logger Logger for error reporting (may be nullptr).
    /// @param toolchain_runfiles_path Runfiles-relative path to the Python toolchain interpreter.
    ///
    /// Toolchain resolution order:
    ///   1. Bazel runfiles (argv[0] + toolchain_runfiles_path)
    ///   2. PYTHONHOME environment variable
    ///   3. python3/python on PATH
    [[nodiscard]] static auto create(char** argv, spdlog::logger* logger,
                                     std::string_view toolchain_runfiles_path)
        -> std::unique_ptr<EmbeddedPythonRuntime>;

    /// Finalizes the Python interpreter (Py_FinalizeEx).
    /// Caller must ensure: GIL held, all subinterpreters ended, no Python threads running.
    ~EmbeddedPythonRuntime();

    EmbeddedPythonRuntime(const EmbeddedPythonRuntime&) = delete;
    auto operator=(const EmbeddedPythonRuntime&) -> EmbeddedPythonRuntime& = delete;
    EmbeddedPythonRuntime(EmbeddedPythonRuntime&&) = delete;
    auto operator=(EmbeddedPythonRuntime&&) -> EmbeddedPythonRuntime& = delete;

    // ─── Status ──────────────────────────────────────────────────────────

    [[nodiscard]] auto version() const -> std::string_view;

    // ─── Library Path Management ──────────────────────────────────────

    /// Registers a runfiles-relative library path for later resolution.
    /// @pre is_resolved() == false
    void add_python_library_path(std::string_view library_relative_path);

    /// Resolves all registered paths (runfiles, then PYTHON_LIB_PATH env fallback).
    /// After success, no further add_python_library_path() calls are allowed.
    /// @pre is_resolved() == false
    [[nodiscard]] auto resolve_python_library_paths() -> bool;

    [[nodiscard]] auto is_resolved() const -> bool;
    [[nodiscard]] auto get_python_library_paths() const -> const std::vector<std::string>&;

    // ─── GIL Management ─────────────────────────────────────────────────

    /// Releases the GIL. Call before spawning threads that use call_in_subinterpreter().
    /// @pre The calling thread holds the GIL.
    [[nodiscard]] auto release_gil() const -> GilReleaseGuard;

    // ─── Subinterpreter Execution ───────────────────────────────────────

    /// Executes function_name(args...) from module_name in an isolated subinterpreter.
    /// Thread-safe: each call creates a subinterpreter with its own GIL.
    ///
    /// @tparam R Return type (default: std::string). Supported: std::string, int,
    ///           long long, double, bool.
    ///
    /// @pre is_resolved() == true
    /// @pre The calling thread does NOT hold the GIL.
    template <typename R = std::string>
    [[nodiscard]] auto call_in_subinterpreter(std::string_view instance_id,
                                              std::string_view module_name,
                                              std::string_view function_name,
                                              std::initializer_list<PyArg> args = {}) const
        -> std::optional<R>;

private:
    EmbeddedPythonRuntime(char** argv, spdlog::logger* logger);

    [[nodiscard]] auto call_in_subinterpreter_impl(std::string_view instance_id,
                                                   std::string_view module_name,
                                                   std::string_view function_name,
                                                   std::span<const PyArg> args,
                                                   PyResultConverterFn converter,
                                                   void* out) const -> bool;

    char** argv_;
    std::vector<std::string> pending_python_library_paths_;
    std::vector<std::string> python_library_paths_;
    spdlog::logger* logger_;
    bool resolved_ = false;
};

// ─── Template Definition ─────────────────────────────────────────────────

template <typename R>
auto EmbeddedPythonRuntime::call_in_subinterpreter(
    std::string_view instance_id, std::string_view module_name,
    std::string_view function_name, std::initializer_list<PyArg> args) const -> std::optional<R> {
    R result{};
    if (call_in_subinterpreter_impl(instance_id, module_name, function_name,
                                    std::span<const PyArg>(args.begin(), args.size()),
                                    &PyResultConverter<R>::convert, &result)) {
        return result;
    }
    return std::nullopt;
}
