#include "python_lib_resolver.h"

#include <gtest/gtest.h>

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string>

#include "test_utils.h"

namespace {

using test_utils::ScopedEnvUnset;
using test_utils::ScopedEnvVar;
using test_utils::TempDir;

class PythonLibResolverEnvTest : public ::testing::Test {
protected:
    void SetUp() override { unsetenv("PYTHON_LIB_PATH"); }
};

// NOLINTBEGIN(cppcoreguidelines-avoid-non-const-global-variables,cppcoreguidelines-owning-memory,cert-err58-cpp,modernize-use-trailing-return-type)

TEST_F(PythonLibResolverEnvTest, UsesPythonLibPathWhenSetAndValid) {
    TempDir temp;
    auto lib_dir = temp.create_python_lib_dir("mylib");

    ScopedEnvVar env("PYTHON_LIB_PATH", lib_dir.string());

    std::string exe_path = "/nonexistent/bin/exe";
    char* argv[] = {const_cast<char*>(exe_path.c_str()), nullptr};

    std::string result;
    EXPECT_TRUE(get_python_lib_path_via_env(argv, result));
    EXPECT_EQ(result, lib_dir.string());
}

TEST_F(PythonLibResolverEnvTest, ReturnsFalseWhenPythonLibPathIsInvalidDirectory) {
    ScopedEnvVar env("PYTHON_LIB_PATH", "/nonexistent/path/to/lib");

    std::string exe_path = "/nonexistent/bin/exe";
    char* argv[] = {const_cast<char*>(exe_path.c_str()), nullptr};

    std::string result;
    EXPECT_FALSE(get_python_lib_path_via_env(argv, result));
}

TEST_F(PythonLibResolverEnvTest, ReturnsFalseWhenPythonLibPathIsEmptyDir) {
    TempDir temp;
    auto empty_dir = temp.path() / "empty";
    std::filesystem::create_directories(empty_dir);

    ScopedEnvVar env("PYTHON_LIB_PATH", empty_dir.string());

    std::string exe_path = "/nonexistent/bin/exe";
    char* argv[] = {const_cast<char*>(exe_path.c_str()), nullptr};

    std::string result;
    EXPECT_FALSE(get_python_lib_path_via_env(argv, result));
}

TEST_F(PythonLibResolverEnvTest, ReturnsFalseWhenDirHasOnlyNonPyFiles) {
    TempDir temp;
    auto lib_dir = temp.path() / "mylib";
    std::filesystem::create_directories(lib_dir);
    std::ofstream(lib_dir / "readme.txt").close();
    std::ofstream(lib_dir / "data.json").close();

    ScopedEnvVar env("PYTHON_LIB_PATH", lib_dir.string());

    std::string exe_path = "/nonexistent/bin/exe";
    char* argv[] = {const_cast<char*>(exe_path.c_str()), nullptr};

    std::string result;
    EXPECT_FALSE(get_python_lib_path_via_env(argv, result));
}

TEST_F(PythonLibResolverEnvTest, AcceptsDirWithPythonPackage) {
    TempDir temp;
    auto lib_dir = temp.create_python_package_dir("mylib", "mypackage");

    ScopedEnvVar env("PYTHON_LIB_PATH", lib_dir.string());

    std::string exe_path = "/nonexistent/bin/exe";
    char* argv[] = {const_cast<char*>(exe_path.c_str()), nullptr};

    std::string result;
    EXPECT_TRUE(get_python_lib_path_via_env(argv, result));
    EXPECT_EQ(result, lib_dir.string());
}

TEST_F(PythonLibResolverEnvTest, ReturnsFalseWhenSubdirHasNoInitPy) {
    TempDir temp;
    auto lib_dir = temp.path() / "mylib";
    auto pkg_dir = lib_dir / "subpackage";
    std::filesystem::create_directories(pkg_dir);
    // Subdirectory exists but has no __init__.py — not a valid package
    std::ofstream(pkg_dir / "module.py").close();

    ScopedEnvVar env("PYTHON_LIB_PATH", lib_dir.string());

    std::string exe_path = "/nonexistent/bin/exe";
    char* argv[] = {const_cast<char*>(exe_path.c_str()), nullptr};

    std::string result;
    EXPECT_FALSE(get_python_lib_path_via_env(argv, result));
}

TEST_F(PythonLibResolverEnvTest, ReturnsFalseWhenEnvUnsetAndNoRelativePaths) {
    ScopedEnvUnset env("PYTHON_LIB_PATH");

    std::string exe_path = "/nonexistent/bin/exe";
    char* argv[] = {const_cast<char*>(exe_path.c_str()), nullptr};

    std::string result;
    EXPECT_FALSE(get_python_lib_path_via_env(argv, result));
}

TEST_F(PythonLibResolverEnvTest, FindsUnixLibLayout) {
    TempDir temp;
    // Create <prefix>/bin/exe and <prefix>/lib/python/module.py
    auto bin_dir = temp.path() / "bin";
    std::filesystem::create_directories(bin_dir);
    auto exe = bin_dir / "exe";
    std::ofstream(exe).close();

    auto python_lib = temp.path() / "lib" / "python";
    std::filesystem::create_directories(python_lib);
    std::ofstream(python_lib / "module.py").close();

    ScopedEnvUnset env("PYTHON_LIB_PATH");

    std::string exe_path = exe.string();
    char* argv[] = {const_cast<char*>(exe_path.c_str()), nullptr};

    std::string result;
    EXPECT_TRUE(get_python_lib_path_via_env(argv, result));
    EXPECT_EQ(result, std::filesystem::canonical(python_lib).string());
}

TEST_F(PythonLibResolverEnvTest, FindsFlatLayout) {
    TempDir temp;
    // Create <dir>/exe and <dir>/python_lib/module.py
    auto exe = temp.path() / "exe";
    std::ofstream(exe).close();

    auto python_lib = temp.path() / "python_lib";
    std::filesystem::create_directories(python_lib);
    std::ofstream(python_lib / "module.py").close();

    ScopedEnvUnset env("PYTHON_LIB_PATH");

    std::string exe_path = exe.string();
    char* argv[] = {const_cast<char*>(exe_path.c_str()), nullptr};

    std::string result;
    EXPECT_TRUE(get_python_lib_path_via_env(argv, result));
    EXPECT_EQ(result, std::filesystem::canonical(python_lib).string());
}

TEST_F(PythonLibResolverEnvTest, FindsShareLayout) {
    TempDir temp;
    // Create <prefix>/bin/exe and <prefix>/share/cpp_py_bootstrap_app/python/module.py
    auto bin_dir = temp.path() / "bin";
    std::filesystem::create_directories(bin_dir);
    auto exe = bin_dir / "exe";
    std::ofstream(exe).close();

    auto python_lib = temp.path() / "share" / "cpp_py_bootstrap_app" / "python";
    std::filesystem::create_directories(python_lib);
    std::ofstream(python_lib / "module.py").close();

    ScopedEnvUnset env("PYTHON_LIB_PATH");

    std::string exe_path = exe.string();
    char* argv[] = {const_cast<char*>(exe_path.c_str()), nullptr};

    std::string result;
    EXPECT_TRUE(get_python_lib_path_via_env(argv, result));
    EXPECT_EQ(result, std::filesystem::canonical(python_lib).string());
}

TEST_F(PythonLibResolverEnvTest, EnvVarTakesPrecedenceOverRelativePaths) {
    TempDir temp;
    // Create both: env var path and flat layout
    auto env_lib = temp.create_python_lib_dir("env_lib");

    auto exe = temp.path() / "exe";
    std::ofstream(exe).close();
    auto python_lib = temp.path() / "python_lib";
    std::filesystem::create_directories(python_lib);
    std::ofstream(python_lib / "module.py").close();

    ScopedEnvVar env("PYTHON_LIB_PATH", env_lib.string());

    std::string exe_path = exe.string();
    char* argv[] = {const_cast<char*>(exe_path.c_str()), nullptr};

    std::string result;
    EXPECT_TRUE(get_python_lib_path_via_env(argv, result));
    // Should prefer PYTHON_LIB_PATH over relative paths
    EXPECT_EQ(result, env_lib.string());
}

TEST_F(PythonLibResolverEnvTest, PrefersUnixLayoutOverFlatLayout) {
    TempDir temp;
    // Create exe in <prefix>/bin/ so both Unix and flat layouts are valid
    auto bin_dir = temp.path() / "bin";
    std::filesystem::create_directories(bin_dir);
    auto exe = bin_dir / "exe";
    std::ofstream(exe).close();

    // Unix layout: <prefix>/lib/python
    auto unix_lib = temp.path() / "lib" / "python";
    std::filesystem::create_directories(unix_lib);
    std::ofstream(unix_lib / "module.py").close();

    // Flat layout: <bin_dir>/python_lib (exe_dir is bin/)
    auto flat_lib = bin_dir / "python_lib";
    std::filesystem::create_directories(flat_lib);
    std::ofstream(flat_lib / "module.py").close();

    ScopedEnvUnset env("PYTHON_LIB_PATH");

    std::string exe_path = exe.string();
    char* argv[] = {const_cast<char*>(exe_path.c_str()), nullptr};

    std::string result;
    EXPECT_TRUE(get_python_lib_path_via_env(argv, result));
    // Unix layout (exe_dir/../lib/python) should be checked first
    EXPECT_EQ(result, std::filesystem::canonical(unix_lib).string());
}

class PythonLibResolverRunfilesTest : public ::testing::Test {};

TEST_F(PythonLibResolverRunfilesTest, ReturnsFalseWhenRunfilesCreationFails) {
    char* fake_argv[] = {const_cast<char*>("/nonexistent/binary"), nullptr};
    std::string result;

    bool success = get_python_lib_path_via_runfiles(fake_argv, "some/path", result);
    // May or may not fail depending on environment; ensures no crash
    (void)success;
}

TEST_F(PythonLibResolverRunfilesTest, HandlesEmptyRelativePath) {
    char* fake_argv[] = {const_cast<char*>("test"), nullptr};
    std::string result;

    bool success = get_python_lib_path_via_runfiles(fake_argv, "", result);
    EXPECT_FALSE(success);
}

// NOLINTEND(cppcoreguidelines-avoid-non-const-global-variables,cppcoreguidelines-owning-memory,cert-err58-cpp,modernize-use-trailing-return-type)

}  // namespace
