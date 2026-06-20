#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <gtest/gtest.h>

#include "spdlog/sinks/null_sink.h"
#include "spdlog/spdlog.h"

namespace test_utils {
// NOLINTNEXTLINE(cppcoreguidelines-avoid-non-const-global-variables)
spdlog::logger* g_test_logger = nullptr;
}  // namespace test_utils

/// Python is process-global, so we initialize once for the entire test binary
/// using a GTest Environment rather than per-fixture SetUp/TearDown.
class PythonEnvironment : public ::testing::Environment {
public:
    void SetUp() override { Py_Initialize(); }

    void TearDown() override { Py_FinalizeEx(); }
};

// NOLINTBEGIN(cppcoreguidelines-owning-memory,modernize-use-trailing-return-type)
auto main(int argc, char** argv) -> int {
    auto null_logger = spdlog::create<spdlog::sinks::null_sink_mt>("test");
    test_utils::g_test_logger = null_logger.get();

    ::testing::InitGoogleTest(&argc, argv);
    ::testing::AddGlobalTestEnvironment(new PythonEnvironment);
    return RUN_ALL_TESTS();
}
// NOLINTEND(cppcoreguidelines-owning-memory,modernize-use-trailing-return-type)
