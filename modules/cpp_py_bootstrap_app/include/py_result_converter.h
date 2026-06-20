#pragma once

#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <string>

#include "spdlog/logger.h"

/// Function pointer type for type-erased result conversion.
/// Converts a PyObject* result into a C++ value stored at @p out.
/// Returns true on success, false on failure (logs errors via @p logger).
using PyResultConverterFn = auto (*)(spdlog::logger* logger, PyObject* result, void* out) -> bool;

/// Primary template — intentionally undefined so unsupported types produce a linker error.
template <typename T>
struct PyResultConverter;

template <>
struct PyResultConverter<std::string> {
    static auto convert(spdlog::logger* logger, PyObject* result, void* out) -> bool {
        if (!PyUnicode_Check(result)) {  // NOLINT(hicpp-signed-bitwise)
            logger->error("Result is not a string");
            return false;
        }
        const char* str = PyUnicode_AsUTF8(result);
        if (str == nullptr) {
            logger->error("Failed to convert result to UTF-8");
            PyErr_Print();
            return false;
        }
        *static_cast<std::string*>(out) = str;
        return true;
    }
};

template <>
struct PyResultConverter<int> {
    static auto convert(spdlog::logger* logger, PyObject* result, void* out) -> bool {
        if (!PyLong_Check(result)) {  // NOLINT(hicpp-signed-bitwise)
            logger->error("Result is not an integer");
            return false;
        }
        const long value = PyLong_AsLong(result);
        if (value == -1 && PyErr_Occurred() != nullptr) {
            logger->error("Failed to convert result to int");
            PyErr_Print();
            return false;
        }
        *static_cast<int*>(out) = static_cast<int>(value);
        return true;
    }
};

template <>
struct PyResultConverter<long long> {
    static auto convert(spdlog::logger* logger, PyObject* result, void* out) -> bool {
        if (!PyLong_Check(result)) {  // NOLINT(hicpp-signed-bitwise)
            logger->error("Result is not an integer");
            return false;
        }
        const long long value = PyLong_AsLongLong(result);
        if (value == -1 && PyErr_Occurred() != nullptr) {
            logger->error("Failed to convert result to long long");
            PyErr_Print();
            return false;
        }
        *static_cast<long long*>(out) = value;
        return true;
    }
};

template <>
struct PyResultConverter<double> {
    static auto convert(spdlog::logger* logger, PyObject* result, void* out) -> bool {
        const double value = PyFloat_AsDouble(result);
        if (value == -1.0 && PyErr_Occurred() != nullptr) {
            logger->error("Result is not a number");
            PyErr_Print();
            return false;
        }
        *static_cast<double*>(out) = value;
        return true;
    }
};

template <>
struct PyResultConverter<bool> {
    static auto convert(spdlog::logger* logger, PyObject* result, void* out) -> bool {
        const int value = PyObject_IsTrue(result);
        if (value == -1) {
            logger->error("Failed to convert result to bool");
            PyErr_Print();
            return false;
        }
        *static_cast<bool*>(out) = (value != 0);
        return true;
    }
};
