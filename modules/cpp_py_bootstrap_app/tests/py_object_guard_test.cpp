#define PY_SSIZE_T_CLEAN
#include "py_object_guard.h"

#include <Python.h>
#include <gtest/gtest.h>

#include <utility>

namespace {

// NOLINTBEGIN(cppcoreguidelines-avoid-non-const-global-variables,cppcoreguidelines-owning-memory,cert-err58-cpp,modernize-use-trailing-return-type)

TEST(PyObjectGuardTest, DefaultConstructorIsNull) {
    PyObjectGuard guard;
    EXPECT_FALSE(static_cast<bool>(guard));
    EXPECT_EQ(guard.get(), nullptr);
}

TEST(PyObjectGuardTest, ConstructorTakesOwnership) {
    PyObject* obj = PyList_New(0);
    ASSERT_NE(obj, nullptr);
    Py_ssize_t initial_refcount = Py_REFCNT(obj);

    PyObjectGuard guard(obj);
    EXPECT_TRUE(static_cast<bool>(guard));
    EXPECT_EQ(guard.get(), obj);
    EXPECT_EQ(Py_REFCNT(obj), initial_refcount);
}

TEST(PyObjectGuardTest, DestructorDecrementsRefCount) {
    PyObject* obj = PyList_New(0);
    ASSERT_NE(obj, nullptr);
    Py_INCREF(obj);  // Extra ref so object survives guard destruction
    Py_ssize_t refcount_before = Py_REFCNT(obj);

    {
        PyObjectGuard guard(obj);
    }
    EXPECT_EQ(Py_REFCNT(obj), refcount_before - 1);
    Py_DECREF(obj);  // Release our extra reference
}

TEST(PyObjectGuardTest, BoolOperatorTrueForNonNull) {
    PyObjectGuard guard(PyList_New(0));
    EXPECT_TRUE(static_cast<bool>(guard));
}

TEST(PyObjectGuardTest, BoolOperatorFalseForNull) {
    PyObjectGuard guard(nullptr);
    EXPECT_FALSE(static_cast<bool>(guard));
}

TEST(PyObjectGuardTest, GetReturnsRawPointer) {
    PyObject* obj = PyList_New(0);
    PyObjectGuard guard(obj);
    EXPECT_EQ(guard.get(), obj);
}

TEST(PyObjectGuardTest, ReleaseTransfersOwnership) {
    PyObject* obj = PyList_New(0);
    PyObjectGuard guard(obj);

    PyObject* released = guard.release();
    EXPECT_EQ(released, obj);
    EXPECT_EQ(guard.get(), nullptr);
    EXPECT_FALSE(static_cast<bool>(guard));

    Py_DECREF(released);  // Caller now owns the reference
}

TEST(PyObjectGuardTest, ReleaseDoesNotDecRef) {
    PyObject* obj = PyList_New(0);
    Py_ssize_t initial_refcount = Py_REFCNT(obj);

    PyObjectGuard guard(obj);
    PyObject* released = guard.release();

    EXPECT_EQ(Py_REFCNT(released), initial_refcount);

    Py_DECREF(released);
}

TEST(PyObjectGuardTest, ResetDecRefsOldAndTakesNew) {
    PyObject* old_obj = PyList_New(0);
    PyObject* new_obj = PyDict_New();
    ASSERT_NE(old_obj, nullptr);
    ASSERT_NE(new_obj, nullptr);

    Py_INCREF(old_obj);  // Extra ref so old_obj survives reset
    Py_ssize_t old_refcount = Py_REFCNT(old_obj);

    PyObjectGuard guard(old_obj);
    guard.reset(new_obj);

    EXPECT_EQ(guard.get(), new_obj);
    // old_obj's refcount should be decremented by reset
    EXPECT_EQ(Py_REFCNT(old_obj), old_refcount - 1);

    Py_DECREF(old_obj);  // Release extra ref
}

TEST(PyObjectGuardTest, ResetToNullDecRefsOld) {
    PyObject* obj = PyList_New(0);
    ASSERT_NE(obj, nullptr);

    Py_INCREF(obj);  // Extra ref
    Py_ssize_t refcount_before = Py_REFCNT(obj);

    PyObjectGuard guard(obj);
    guard.reset();

    EXPECT_EQ(guard.get(), nullptr);
    EXPECT_FALSE(static_cast<bool>(guard));
    EXPECT_EQ(Py_REFCNT(obj), refcount_before - 1);

    Py_DECREF(obj);  // Release extra ref
}

TEST(PyObjectGuardTest, MoveConstructorTransfers) {
    PyObject* obj = PyList_New(0);
    ASSERT_NE(obj, nullptr);
    Py_ssize_t initial_refcount = Py_REFCNT(obj);

    PyObjectGuard source(obj);
    PyObjectGuard dest(std::move(source));

    EXPECT_EQ(dest.get(), obj);
    EXPECT_TRUE(static_cast<bool>(dest));
    EXPECT_EQ(source.get(), nullptr);  // NOLINT(bugprone-use-after-move)
    EXPECT_FALSE(static_cast<bool>(source));
    EXPECT_EQ(Py_REFCNT(obj), initial_refcount);
}

TEST(PyObjectGuardTest, MoveAssignmentTransfers) {
    PyObject* obj1 = PyList_New(0);
    PyObject* obj2 = PyDict_New();
    ASSERT_NE(obj1, nullptr);
    ASSERT_NE(obj2, nullptr);

    Py_INCREF(obj1);  // Extra ref so obj1 survives
    Py_ssize_t obj1_refcount = Py_REFCNT(obj1);

    PyObjectGuard dest(obj1);
    PyObjectGuard source(obj2);

    dest = std::move(source);

    EXPECT_EQ(dest.get(), obj2);
    EXPECT_EQ(source.get(), nullptr);  // NOLINT(bugprone-use-after-move)
    // obj1 should have been decremented by move assignment
    EXPECT_EQ(Py_REFCNT(obj1), obj1_refcount - 1);

    Py_DECREF(obj1);  // Release extra ref
}

// NOLINTEND(cppcoreguidelines-avoid-non-const-global-variables,cppcoreguidelines-owning-memory,cert-err58-cpp,modernize-use-trailing-return-type)

}  // namespace
