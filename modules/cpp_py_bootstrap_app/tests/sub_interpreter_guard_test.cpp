#define PY_SSIZE_T_CLEAN
#include "sub_interpreter_guard.h"

#include <Python.h>
#include <gtest/gtest.h>

namespace {

// NOLINTBEGIN(cppcoreguidelines-avoid-non-const-global-variables,cppcoreguidelines-owning-memory,cert-err58-cpp,modernize-use-trailing-return-type)

TEST(SubInterpreterGuardTest, DefaultStateBeforeCreate) {
    PyThreadState* main_ts = PyThreadState_Get();
    SubInterpreterGuard guard(main_ts);

    EXPECT_FALSE(static_cast<bool>(guard));
    EXPECT_EQ(guard.get(), nullptr);
}

TEST(SubInterpreterGuardTest, CreateSucceeds) {
    PyThreadState* main_ts = PyThreadState_Get();
    SubInterpreterGuard guard(main_ts);

    ASSERT_TRUE(guard.create());
    EXPECT_TRUE(static_cast<bool>(guard));
    EXPECT_NE(guard.get(), nullptr);
    EXPECT_EQ(PyThreadState_Get(), guard.get());
}

TEST(SubInterpreterGuardTest, SubInterpreterHasOwnState) {
    PyThreadState* main_ts = PyThreadState_Get();
    SubInterpreterGuard guard(main_ts);

    ASSERT_TRUE(guard.create());
    EXPECT_NE(guard.get(), main_ts);
}

TEST(SubInterpreterGuardTest, DestructorRestoresMainThreadState) {
    PyThreadState* main_ts = PyThreadState_Get();
    {
        SubInterpreterGuard guard(main_ts);
        ASSERT_TRUE(guard.create());
        EXPECT_NE(PyThreadState_Get(), main_ts);
    }
    EXPECT_EQ(PyThreadState_Get(), main_ts);
}

TEST(SubInterpreterGuardTest, SubInterpreterCanRunPython) {
    PyThreadState* main_ts = PyThreadState_Get();
    SubInterpreterGuard guard(main_ts);
    ASSERT_TRUE(guard.create());

    int result = PyRun_SimpleString("x = 1 + 1\nassert x == 2");
    EXPECT_EQ(result, 0);
}

TEST(SubInterpreterGuardTest, NullLogger) {
    PyThreadState* main_ts = PyThreadState_Get();
    SubInterpreterGuard guard(main_ts, static_cast<spdlog::logger*>(nullptr));

    ASSERT_TRUE(guard.create());
    EXPECT_TRUE(static_cast<bool>(guard));
}

// NOLINTEND(cppcoreguidelines-avoid-non-const-global-variables,cppcoreguidelines-owning-memory,cert-err58-cpp,modernize-use-trailing-return-type)

}  // namespace
