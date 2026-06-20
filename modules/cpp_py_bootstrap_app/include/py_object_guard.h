#pragma once

#define PY_SSIZE_T_CLEAN
#include <Python.h>

/// RAII wrapper for PyObject* (calls Py_XDECREF on destruction).
/// Follows the "stolen reference" pattern — constructing a PyObjectGuard takes
/// ownership of the reference and will decrement it when destroyed.
class PyObjectGuard {
public:
    explicit PyObjectGuard(PyObject* obj = nullptr) : obj_(obj) {}

    ~PyObjectGuard() { Py_XDECREF(obj_); }

    // Non-copyable (copying would require incrementing refcount)
    PyObjectGuard(const PyObjectGuard&) = delete;
    auto operator=(const PyObjectGuard&) -> PyObjectGuard& = delete;

    PyObjectGuard(PyObjectGuard&& other) noexcept : obj_(other.obj_) { other.obj_ = nullptr; }

    auto operator=(PyObjectGuard&& other) noexcept -> PyObjectGuard& {
        if (this != &other) {
            Py_XDECREF(obj_);
            obj_ = other.obj_;
            other.obj_ = nullptr;
        }
        return *this;
    }

    [[nodiscard]] auto get() const -> PyObject* { return obj_; }

    [[nodiscard]] explicit operator bool() const { return obj_ != nullptr; }

    /// Releases ownership without decrementing refcount.
    auto release() -> PyObject* {
        PyObject* const tmp = obj_;  // NOLINT(misc-const-correctness) — pointee must stay non-const for return type
        obj_ = nullptr;
        return tmp;
    }

    /// Replaces the managed object (decrefs the old one).
    void reset(PyObject* obj = nullptr) {
        Py_XDECREF(obj_);
        obj_ = obj;
    }

private:
    PyObject* obj_;
};
