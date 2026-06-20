#define PY_SSIZE_T_CLEAN
#include "py_result_converter.h"

#include <Python.h>
#include <gtest/gtest.h>

#include <string>

#include "spdlog/logger.h"

namespace test_utils {
extern spdlog::logger* g_test_logger;  // defined in python_test_main.cpp
}  // namespace test_utils

namespace {
auto logger() -> spdlog::logger* { return test_utils::g_test_logger; }
}  // namespace

TEST(PyResultConverterString, ConvertsUnicodeString) {
    PyObject* obj = PyUnicode_FromString("hello world");
    ASSERT_NE(obj, nullptr);

    std::string result;
    EXPECT_TRUE(PyResultConverter<std::string>::convert(logger(), obj, &result));
    EXPECT_EQ(result, "hello world");

    Py_DECREF(obj);
}

TEST(PyResultConverterString, RejectsNonString) {
    PyObject* obj = PyLong_FromLong(42);
    ASSERT_NE(obj, nullptr);

    std::string result;
    EXPECT_FALSE(PyResultConverter<std::string>::convert(logger(), obj, &result));

    Py_DECREF(obj);
}

TEST(PyResultConverterInt, ConvertsInteger) {
    PyObject* obj = PyLong_FromLong(42);
    ASSERT_NE(obj, nullptr);

    int result = 0;
    EXPECT_TRUE(PyResultConverter<int>::convert(logger(), obj, &result));
    EXPECT_EQ(result, 42);

    Py_DECREF(obj);
}

TEST(PyResultConverterInt, ConvertsNegativeInteger) {
    PyObject* obj = PyLong_FromLong(-100);
    ASSERT_NE(obj, nullptr);

    int result = 0;
    EXPECT_TRUE(PyResultConverter<int>::convert(logger(), obj, &result));
    EXPECT_EQ(result, -100);

    Py_DECREF(obj);
}

TEST(PyResultConverterInt, RejectsNonInteger) {
    PyObject* obj = PyUnicode_FromString("not a number");
    ASSERT_NE(obj, nullptr);

    int result = 0;
    EXPECT_FALSE(PyResultConverter<int>::convert(logger(), obj, &result));

    Py_DECREF(obj);
}

TEST(PyResultConverterLongLong, ConvertsLargeInteger) {
    PyObject* obj = PyLong_FromLongLong(9'000'000'000LL);
    ASSERT_NE(obj, nullptr);

    long long result = 0;
    EXPECT_TRUE(PyResultConverter<long long>::convert(logger(), obj, &result));
    EXPECT_EQ(result, 9'000'000'000LL);

    Py_DECREF(obj);
}

TEST(PyResultConverterLongLong, RejectsNonInteger) {
    PyObject* obj = PyFloat_FromDouble(3.14);
    ASSERT_NE(obj, nullptr);

    long long result = 0;
    EXPECT_FALSE(PyResultConverter<long long>::convert(logger(), obj, &result));

    Py_DECREF(obj);
}

TEST(PyResultConverterDouble, ConvertsFloat) {
    PyObject* obj = PyFloat_FromDouble(3.14);
    ASSERT_NE(obj, nullptr);

    double result = 0.0;
    EXPECT_TRUE(PyResultConverter<double>::convert(logger(), obj, &result));
    EXPECT_DOUBLE_EQ(result, 3.14);

    Py_DECREF(obj);
}

TEST(PyResultConverterDouble, ConvertsPythonIntToDouble) {
    // PyFloat_AsDouble accepts Python int objects (promotes them)
    PyObject* obj = PyLong_FromLong(42);
    ASSERT_NE(obj, nullptr);

    double result = 0.0;
    EXPECT_TRUE(PyResultConverter<double>::convert(logger(), obj, &result));
    EXPECT_DOUBLE_EQ(result, 42.0);

    Py_DECREF(obj);
}

TEST(PyResultConverterDouble, RejectsNonNumeric) {
    PyObject* obj = PyUnicode_FromString("not a number");
    ASSERT_NE(obj, nullptr);

    double result = 0.0;
    EXPECT_FALSE(PyResultConverter<double>::convert(logger(), obj, &result));

    // PyFloat_AsDouble sets an error on non-numeric types
    PyErr_Clear();
    Py_DECREF(obj);
}

TEST(PyResultConverterBool, ConvertsTrueValue) {
    bool result = false;
    EXPECT_TRUE(PyResultConverter<bool>::convert(logger(), Py_True, &result));
    EXPECT_TRUE(result);
}

TEST(PyResultConverterBool, ConvertsFalseValue) {
    bool result = true;
    EXPECT_TRUE(PyResultConverter<bool>::convert(logger(), Py_False, &result));
    EXPECT_FALSE(result);
}

TEST(PyResultConverterBool, ConvertsTruthyNonBool) {
    // PyObject_IsTrue works on any Python object (non-zero int is truthy)
    PyObject* obj = PyLong_FromLong(42);
    ASSERT_NE(obj, nullptr);

    bool result = false;
    EXPECT_TRUE(PyResultConverter<bool>::convert(logger(), obj, &result));
    EXPECT_TRUE(result);

    Py_DECREF(obj);
}

TEST(PyResultConverterBool, ConvertsFalsyZero) {
    PyObject* obj = PyLong_FromLong(0);
    ASSERT_NE(obj, nullptr);

    bool result = true;
    EXPECT_TRUE(PyResultConverter<bool>::convert(logger(), obj, &result));
    EXPECT_FALSE(result);

    Py_DECREF(obj);
}
