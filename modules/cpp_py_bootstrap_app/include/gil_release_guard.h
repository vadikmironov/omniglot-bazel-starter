#pragma once

#define PY_SSIZE_T_CLEAN
#include <Python.h>

/// RAII guard: releases the GIL on construction, reacquires on destruction.
///
/// After Py_Initialize, the calling thread holds the GIL. Before spawning threads that
/// need to call into Python (via PyGILState_Ensure), the main thread must release the
/// GIL. This guard automates that pattern.
class GilReleaseGuard {
public:
    GilReleaseGuard() : thread_state_(PyEval_SaveThread()) {}

    ~GilReleaseGuard() {
        if (thread_state_ != nullptr) {
            PyEval_RestoreThread(thread_state_);
        }
    }

    // Non-copyable, non-movable (thread state is bound to calling thread)
    GilReleaseGuard(const GilReleaseGuard&) = delete;
    auto operator=(const GilReleaseGuard&) -> GilReleaseGuard& = delete;
    GilReleaseGuard(GilReleaseGuard&&) = delete;
    auto operator=(GilReleaseGuard&&) -> GilReleaseGuard& = delete;

private:
    PyThreadState* thread_state_;
};
