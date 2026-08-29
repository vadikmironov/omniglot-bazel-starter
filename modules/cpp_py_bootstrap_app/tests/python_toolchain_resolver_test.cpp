#include "python_toolchain_resolver.h"

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

class PythonToolchainEnvTest : public ::testing::Test {
protected:
    void SetUp() override { test_utils::unset_env("PYTHONHOME"); }
};

// NOLINTBEGIN(cppcoreguidelines-avoid-non-const-global-variables,cppcoreguidelines-owning-memory,cert-err58-cpp,modernize-use-trailing-return-type)

TEST_F(PythonToolchainEnvTest, UsesPythonHomeWhenSetAndValid) {
    TempDir temp;
    temp.create_python_layout();

    ScopedEnvVar pythonhome("PYTHONHOME", temp.path().string());

    std::string result;
    EXPECT_TRUE(get_python_toolchain_path_via_env(result));
    EXPECT_EQ(result, temp.path().string());
}

TEST_F(PythonToolchainEnvTest, ReturnsFalseWhenPythonHomeIsInvalidDirectory) {
    ScopedEnvVar pythonhome("PYTHONHOME", "/nonexistent/path/to/python");
    // Also clear PATH to prevent fallback to system Python
    ScopedEnvUnset path("PATH");

    std::string result;
    EXPECT_FALSE(get_python_toolchain_path_via_env(result));
}

TEST_F(PythonToolchainEnvTest, FindsPython3InPath) {
    TempDir temp;
    temp.create_python_layout("python3");

    ScopedEnvVar path("PATH", temp.bin_dir().string());

    std::string result;
    EXPECT_TRUE(get_python_toolchain_path_via_env(result));
    EXPECT_EQ(result, temp.path().string());
}

TEST_F(PythonToolchainEnvTest, FallsBackToPythonWhenPython3NotFound) {
    TempDir temp;
    temp.create_python_layout("python");

    ScopedEnvVar path("PATH", temp.bin_dir().string());

    std::string result;
    EXPECT_TRUE(get_python_toolchain_path_via_env(result));
    EXPECT_EQ(result, temp.path().string());
}

TEST_F(PythonToolchainEnvTest, ReturnsFalseWhenPathNotSet) {
    ScopedEnvUnset path("PATH");

    std::string result;
    EXPECT_FALSE(get_python_toolchain_path_via_env(result));
}

TEST_F(PythonToolchainEnvTest, ReturnsFalseWhenNoValidPythonInPath) {
    TempDir temp;
    // Create directory without any Python interpreter

    ScopedEnvVar path("PATH", temp.path().string());

    std::string result;
    EXPECT_FALSE(get_python_toolchain_path_via_env(result));
}

TEST_F(PythonToolchainEnvTest, ValidatesPythonHomeHasLibDirectory) {
    TempDir temp;
    temp.create_python_layout_no_lib("python3");

    ScopedEnvVar path("PATH", temp.bin_dir().string());

    std::string result;
    EXPECT_FALSE(get_python_toolchain_path_via_env(result));
}

TEST_F(PythonToolchainEnvTest, HandlesMultiplePathEntries) {
    TempDir temp1;
    TempDir temp2;
    temp2.create_python_layout("python3");

    // First path has no Python, second path has Python
    std::string path_value = temp1.path().string() + test_utils::path_list_sep() + temp2.bin_dir().string();
    ScopedEnvVar path("PATH", path_value);

    std::string result;
    EXPECT_TRUE(get_python_toolchain_path_via_env(result));
    EXPECT_EQ(result, temp2.path().string());
}

TEST_F(PythonToolchainEnvTest, PrefersFirstValidPythonInPath) {
    TempDir temp1;
    TempDir temp2;
    temp1.create_python_layout("python3");
    temp2.create_python_layout("python3");

    std::string path_value = temp1.bin_dir().string() + test_utils::path_list_sep() + temp2.bin_dir().string();
    ScopedEnvVar path("PATH", path_value);

    std::string result;
    EXPECT_TRUE(get_python_toolchain_path_via_env(result));
    EXPECT_EQ(result, temp1.path().string());
}

TEST_F(PythonToolchainEnvTest, SkipsEmptyPathEntries) {
    TempDir temp;
    temp.create_python_layout("python3");

    // PATH with empty entries (::)
    std::string const sep = test_utils::path_list_sep();
    std::string path_value = sep + temp.bin_dir().string() + sep;
    ScopedEnvVar path("PATH", path_value);

    std::string result;
    EXPECT_TRUE(get_python_toolchain_path_via_env(result));
    EXPECT_EQ(result, temp.path().string());
}

TEST_F(PythonToolchainEnvTest, PrefersPythonHomeOverPath) {
    TempDir pythonhome_dir;
    TempDir path_dir;
    pythonhome_dir.create_python_layout("python3");
    path_dir.create_python_layout("python3");

    ScopedEnvVar pythonhome("PYTHONHOME", pythonhome_dir.path().string());
    ScopedEnvVar path("PATH", path_dir.bin_dir().string());

    std::string result;
    EXPECT_TRUE(get_python_toolchain_path_via_env(result));
    // Should prefer PYTHONHOME over PATH
    EXPECT_EQ(result, pythonhome_dir.path().string());
}

TEST_F(PythonToolchainEnvTest, ResolvesSymlinksBeforeDerivingHome) {
    // Real installation lives in real_dir, symlink in symlink_dir/bin points to it
    TempDir real_dir;
    TempDir symlink_dir;
    real_dir.create_python_layout("python3");

    auto symlink_bin = symlink_dir.bin_dir();
    std::filesystem::create_directories(symlink_bin);
    auto const link_name = TempDir::interpreter_name("python3");
    std::error_code link_ec;
    std::filesystem::create_symlink(real_dir.bin_dir() / link_name, symlink_bin / link_name, link_ec);
    if (link_ec) {
        GTEST_SKIP() << "symlink creation unsupported here: " << link_ec.message();
    }

    ScopedEnvVar path("PATH", symlink_bin.string());

    std::string result;
    EXPECT_TRUE(get_python_toolchain_path_via_env(result));
    // Should resolve symlink and find the real installation's home
    EXPECT_EQ(result, real_dir.path().string());
}

TEST_F(PythonToolchainEnvTest, RejectsPathEntryWithoutVersionedStdlib) {
    // Stdlib directory exists but holds no os.py — should be rejected
    TempDir temp;
    auto bin_dir = temp.bin_dir();
#ifdef _WIN32
    auto lib_dir = temp.path() / "Lib";
#else
    auto lib_dir = temp.path() / "lib";
#endif
    std::filesystem::create_directories(bin_dir);
    std::filesystem::create_directories(lib_dir);

    auto interpreter = bin_dir / TempDir::interpreter_name("python3");
    std::ofstream(interpreter).close();
    std::filesystem::permissions(interpreter,
                                 std::filesystem::perms::owner_exec | std::filesystem::perms::owner_read);

    ScopedEnvVar path("PATH", bin_dir.string());

    std::string result;
    EXPECT_FALSE(get_python_toolchain_path_via_env(result));
}

TEST_F(PythonToolchainEnvTest, FallsThroughFromInvalidPythonHomeToPath) {
    TempDir invalid_home;
    // invalid_home has no stdlib — just an empty directory
    std::filesystem::create_directories(invalid_home.path() / "lib");

    TempDir valid_path;
    valid_path.create_python_layout("python3");

    ScopedEnvVar pythonhome("PYTHONHOME", invalid_home.path().string());
    ScopedEnvVar path("PATH", valid_path.bin_dir().string());

    std::string result;
    EXPECT_TRUE(get_python_toolchain_path_via_env(result));
    // Should fall through from invalid PYTHONHOME and find Python via PATH
    EXPECT_EQ(result, valid_path.path().string());
}

TEST_F(PythonToolchainEnvTest, FindsDifferentPythonVersionStdlib) {
#ifdef _WIN32
    GTEST_SKIP() << "Windows stdlib lives at <prefix>/Lib with no version segment";
#else
    // Layout has python3.13 stdlib — resolver should still accept it
    TempDir temp;
    temp.create_python_layout("python3", 3, 13);

    ScopedEnvVar path("PATH", temp.bin_dir().string());

    std::string result;
    EXPECT_TRUE(get_python_toolchain_path_via_env(result));
    EXPECT_EQ(result, temp.path().string());
#endif
}

class PythonToolchainRunfilesTest : public ::testing::Test {};

TEST_F(PythonToolchainRunfilesTest, ReturnsFalseWhenRunfilesCreationFails) {
    // When running outside Bazel with invalid argv, runfiles creation should fail
    char* fake_argv[] = {const_cast<char*>("/nonexistent/binary"), nullptr};
    std::string result;

    // This may or may not fail depending on environment - if running under Bazel
    // it might still work. The test is mainly to ensure no crash occurs.
    bool success = get_python_toolchain_path_via_runfiles(fake_argv, "../some/path/bin/python3", result);

    // We can't assert the exact result since it depends on environment
    // Just ensure the function doesn't crash
    (void)success;
}

TEST_F(PythonToolchainRunfilesTest, HandlesEmptyRelativePath) {
    char* fake_argv[] = {const_cast<char*>("test"), nullptr};
    std::string result;

    bool success = get_python_toolchain_path_via_runfiles(fake_argv, "", result);
    EXPECT_FALSE(success);
}

TEST_F(PythonToolchainRunfilesTest, HandlesPathWithoutPrefix) {
    char* fake_argv[] = {const_cast<char*>("test"), nullptr};
    std::string result;

    // Path without ../ prefix - should still try to process
    bool success = get_python_toolchain_path_via_runfiles(fake_argv, "some_repo/bin/python3", result);
    // Will likely fail because runfiles won't find it, but shouldn't crash
    (void)success;
}

TEST_F(PythonToolchainRunfilesTest, HandlesPathWithoutSuffix) {
    char* fake_argv[] = {const_cast<char*>("test"), nullptr};
    std::string result;

    // Path without /bin/python3 suffix
    bool success = get_python_toolchain_path_via_runfiles(fake_argv, "../some_repo", result);
    // Will likely fail, but shouldn't crash
    (void)success;
}

// NOLINTEND(cppcoreguidelines-avoid-non-const-global-variables,cppcoreguidelines-owning-memory,cert-err58-cpp,modernize-use-trailing-return-type)

}  // namespace
