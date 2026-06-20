#pragma once

#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "spdlog/logger.h"

/// RAII wrapper for Python subinterpreter lifecycle.
///
/// When created with PyInterpreterConfig_OWN_GIL, each subinterpreter has its
/// own GIL, enabling true parallel Python execution across threads.
class SubInterpreterGuard {
public:
    /// For use from Python-created threads.
    explicit SubInterpreterGuard(PyThreadState* main_ts, spdlog::logger* logger = nullptr)
        : main_ts_(main_ts), sub_ts_(nullptr), gil_state_(PyGILState_UNLOCKED), owns_gil_state_(false), logger_(logger) {}

    /// For use from C++ threads (pass the GIL state from PyGILState_Ensure).
    SubInterpreterGuard(PyThreadState* main_ts, PyGILState_STATE gil_state,
                        spdlog::logger* logger = nullptr)
        : main_ts_(main_ts), sub_ts_(nullptr), gil_state_(gil_state), owns_gil_state_(true), logger_(logger) {}

    ~SubInterpreterGuard() {
        if (sub_ts_ != nullptr) {
            Py_EndInterpreter(sub_ts_);
            PyThreadState_Swap(main_ts_);
        }
        if (owns_gil_state_) {
            PyGILState_Release(gil_state_);
        }
    }

    // Non-copyable, non-movable (subinterpreter is tied to thread state)
    SubInterpreterGuard(const SubInterpreterGuard&) = delete;
    auto operator=(const SubInterpreterGuard&) -> SubInterpreterGuard& = delete;
    SubInterpreterGuard(SubInterpreterGuard&&) = delete;
    auto operator=(SubInterpreterGuard&&) -> SubInterpreterGuard& = delete;

    /// Creates a new subinterpreter with its own GIL.
    [[nodiscard]] auto create() -> bool {
        const PyInterpreterConfig config = {
            .use_main_obmalloc = 0,
            .allow_fork = 0,
            .allow_exec = 0,
            .allow_threads = 1,
            .allow_daemon_threads = 0,
            .check_multi_interp_extensions = 1,
            .gil = PyInterpreterConfig_OWN_GIL,
        };

        PyStatus status = Py_NewInterpreterFromConfig(&sub_ts_, &config);
        if (PyStatus_Exception(status) != 0) {
            if (logger_ != nullptr) {
                if (status.err_msg != nullptr) {
                    logger_->error("Failed to create subinterpreter: {}", status.err_msg);
                } else {
                    logger_->error("Failed to create subinterpreter");
                }
            }
            return false;
        }
        return true;
    }

    [[nodiscard]] auto get() const -> PyThreadState* { return sub_ts_; }

    [[nodiscard]] explicit operator bool() const { return sub_ts_ != nullptr; }

private:
    PyThreadState* main_ts_;
    PyThreadState* sub_ts_;
    PyGILState_STATE gil_state_;
    bool owns_gil_state_;
    spdlog::logger* logger_;
};
