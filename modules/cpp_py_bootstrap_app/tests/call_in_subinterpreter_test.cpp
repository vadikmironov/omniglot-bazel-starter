#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <gtest/gtest.h>

#include <memory>
#include <optional>
#include <string>

#include "embedded_python_runtime.h"
#include "rules_python_current_interpreter_path_header.h"
#include "spdlog/sinks/stdout_color_sinks.h"
#include "spdlog/spdlog.h"

namespace {

class PythonEnvironment : public ::testing::Environment {
public:
    explicit PythonEnvironment(char** argv) : argv_(argv) {}

    void SetUp() override {
        auto logger_ptr = spdlog::stderr_color_mt("root");
        logger_ = logger_ptr.get();

        runtime_ = EmbeddedPythonRuntime::create(argv_, logger_, RULES_PYTHON_RUNFILES_PATH);
        ASSERT_NE(runtime_, nullptr);

        runtime_->add_python_library_path("_main/modules/cpp_py_bootstrap_app/tests");
        runtime_->add_python_library_path("_main/modules/python_lib/src");
        ASSERT_TRUE(runtime_->resolve_python_library_paths());

        // GilReleaseGuard is non-movable, so manage PyThreadState directly.
        saved_thread_state_ = PyEval_SaveThread();
    }

    void TearDown() override {
        PyEval_RestoreThread(saved_thread_state_);
        runtime_.reset();
    }

    [[nodiscard]] auto runtime() const -> EmbeddedPythonRuntime* { return runtime_.get(); }

private:
    char** argv_;
    spdlog::logger* logger_ = nullptr;
    std::unique_ptr<EmbeddedPythonRuntime> runtime_;
    PyThreadState* saved_thread_state_ = nullptr;
};

// NOLINTBEGIN(cppcoreguidelines-avoid-non-const-global-variables)
PythonEnvironment* g_env = nullptr;
// NOLINTEND(cppcoreguidelines-avoid-non-const-global-variables)

class CallInSubinterpreterTest : public ::testing::Test {
protected:
    [[nodiscard]] auto runtime() const -> EmbeddedPythonRuntime* { return g_env->runtime(); }
};

TEST_F(CallInSubinterpreterTest, AddNumbersReturnsInt) {
    auto result = runtime()->call_in_subinterpreter<int>(
        "test", "py_test_lib.multi_type_functions", "add_numbers", {10, 20});
    ASSERT_TRUE(result.has_value());
    EXPECT_EQ(*result, 30);
}

TEST_F(CallInSubinterpreterTest, ConcatenateReturnsString) {
    auto result = runtime()->call_in_subinterpreter(
        "test", "py_test_lib.multi_type_functions", "concatenate", {"Hello ", 42, "!"});
    ASSERT_TRUE(result.has_value());
    EXPECT_EQ(*result, "Hello 42!");
}

TEST_F(CallInSubinterpreterTest, IsPositiveTrueReturnsBool) {
    auto result = runtime()->call_in_subinterpreter<bool>(
        "test", "py_test_lib.multi_type_functions", "is_positive", {3.14});
    ASSERT_TRUE(result.has_value());
    EXPECT_TRUE(*result);
}

TEST_F(CallInSubinterpreterTest, IsPositiveFalseReturnsBool) {
    auto result = runtime()->call_in_subinterpreter<bool>(
        "test", "py_test_lib.multi_type_functions", "is_positive", {-1.0});
    ASSERT_TRUE(result.has_value());
    EXPECT_FALSE(*result);
}

TEST_F(CallInSubinterpreterTest, MultiplyReturnsDouble) {
    auto result = runtime()->call_in_subinterpreter<double>(
        "test", "py_test_lib.multi_type_functions", "multiply", {2.5, 4.0});
    ASSERT_TRUE(result.has_value());
    EXPECT_DOUBLE_EQ(*result, 10.0);
}

TEST_F(CallInSubinterpreterTest, GetHelloWorldStringBackwardCompat) {
    auto result = runtime()->call_in_subinterpreter(
        "test", "python_lib.hello_world_lib", "get_hello_world_string", {1});
    ASSERT_TRUE(result.has_value());
    EXPECT_EQ(*result, "Hello, Star!");
}

TEST_F(CallInSubinterpreterTest, GetHelloWorldStringNoArgs) {
    auto result = runtime()->call_in_subinterpreter(
        "test", "python_lib.hello_world_lib", "get_hello_world_string");
    ASSERT_TRUE(result.has_value());
    EXPECT_EQ(*result, "Hello, World!");
}

}  // namespace

// NOLINTBEGIN(cppcoreguidelines-owning-memory)
auto main(int argc, char** argv) -> int {
    ::testing::InitGoogleTest(&argc, argv);
    auto* env = new PythonEnvironment(argv);  // GoogleTest takes ownership
    g_env = env;
    ::testing::AddGlobalTestEnvironment(env);
    return RUN_ALL_TESTS();
}
// NOLINTEND(cppcoreguidelines-owning-memory)
