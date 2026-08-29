#pragma once

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string>

namespace test_utils {

/// MSVC's CRT has no POSIX setenv/unsetenv; _putenv_s covers both, with an
/// empty value removing the variable.
inline void set_env(const char* name, const char* value) {
#ifdef _WIN32
    _putenv_s(name, value);
#else
    setenv(name, value, 1);
#endif
}

inline void unset_env(const char* name) {
#ifdef _WIN32
    _putenv_s(name, "");
#else
    unsetenv(name);
#endif
}

/// PATH entry separator, matching what the resolver splits on.
inline auto path_list_sep() -> const char* {
#ifdef _WIN32
    return ";";
#else
    return ":";
#endif
}

/// RAII helper to temporarily set an environment variable in tests.
class ScopedEnvVar {
public:
    explicit ScopedEnvVar(const std::string& name, const std::string& value) : name_(name) {
        const char* old_value = std::getenv(name.c_str());
        if (old_value != nullptr) {
            had_value_ = true;
            old_value_ = old_value;
        }
        set_env(name.c_str(), value.c_str());
    }

    ~ScopedEnvVar() {
        if (had_value_) {
            set_env(name_.c_str(), old_value_.c_str());
        } else {
            unset_env(name_.c_str());
        }
    }

    ScopedEnvVar(const ScopedEnvVar&) = delete;
    ScopedEnvVar& operator=(const ScopedEnvVar&) = delete;

private:
    std::string name_;
    std::string old_value_;
    bool had_value_ = false;
};

/// RAII helper to temporarily unset an environment variable in tests.
class ScopedEnvUnset {
public:
    explicit ScopedEnvUnset(const std::string& name) : name_(name) {
        const char* old_value = std::getenv(name.c_str());
        if (old_value != nullptr) {
            had_value_ = true;
            old_value_ = old_value;
        }
        unset_env(name.c_str());
    }

    ~ScopedEnvUnset() {
        if (had_value_) {
            set_env(name_.c_str(), old_value_.c_str());
        }
    }

    ScopedEnvUnset(const ScopedEnvUnset&) = delete;
    ScopedEnvUnset& operator=(const ScopedEnvUnset&) = delete;

private:
    std::string name_;
    std::string old_value_;
    bool had_value_ = false;
};

/// RAII helper to create a temporary directory that is cleaned up on destruction.
class TempDir {
public:
    TempDir() {
        path_ = std::filesystem::temp_directory_path() / ("test_py_resolver_" + std::to_string(counter_++));
        std::filesystem::create_directories(path_);
        // Canonicalize to resolve any symlinks in the temp path itself.
        // On macOS, /var -> /private/var, so temp_directory_path() returns
        // /var/folders/... but canonical() returns /private/var/folders/...
        // Without this, test assertions would fail when the resolver uses
        // canonical() during PATH-based lookups.
        path_ = std::filesystem::canonical(path_);
    }

    ~TempDir() { std::filesystem::remove_all(path_); }

    [[nodiscard]] auto path() const -> const std::filesystem::path& { return path_; }

    /// Directory holding the interpreter, i.e. what a test should put on PATH.
    /// Windows Python keeps python.exe at the prefix root; Unix uses bin/.
    [[nodiscard]] auto bin_dir() const -> std::filesystem::path {
#ifdef _WIN32
        return path_;
#else
        return path_ / "bin";
#endif
    }

    /// Interpreter file name as the resolver looks for it.
    [[nodiscard]] static auto interpreter_name(const std::string& name) -> std::string {
#ifdef _WIN32
        return name + ".exe";
#else
        return name;
#endif
    }

    // Create a fake Python installation layout matching what the resolver
    // probes for: Unix <prefix>/bin/<name> + <prefix>/lib/pythonX.Y/os.py,
    // Windows <prefix>/<name>.exe + <prefix>/Lib/os.py (no version segment,
    // so major/minor are Unix-only).
    auto create_python_layout(const std::string& name = "python3",
                              int major = 3, int minor = 14) -> std::filesystem::path {
#ifdef _WIN32
        (void)major;
        (void)minor;
        auto stdlib_dir = path_ / "Lib";
#else
        auto stdlib_dir = path_ / "lib" / ("python" + std::to_string(major) + "." + std::to_string(minor));
#endif
        std::filesystem::create_directories(bin_dir());
        std::filesystem::create_directories(stdlib_dir);

        // Create stdlib marker file
        std::ofstream(stdlib_dir / "os.py").close();

        auto interpreter = bin_dir() / interpreter_name(name);
        std::ofstream(interpreter).close();
        std::filesystem::permissions(interpreter,
                                     std::filesystem::perms::owner_exec | std::filesystem::perms::owner_read);

        return interpreter;
    }

    // Create a Python installation without a stdlib directory (invalid)
    auto create_python_layout_no_lib(const std::string& name = "python3") -> std::filesystem::path {
        std::filesystem::create_directories(bin_dir());

        auto interpreter = bin_dir() / interpreter_name(name);
        std::ofstream(interpreter).close();
        std::filesystem::permissions(interpreter,
                                     std::filesystem::perms::owner_exec | std::filesystem::perms::owner_read);

        return interpreter;
    }

    // Create a directory containing .py files (valid Python lib path)
    auto create_python_lib_dir(const std::string& dir_name = "python_lib") -> std::filesystem::path {
        auto lib_dir = path_ / dir_name;
        std::filesystem::create_directories(lib_dir);
        std::ofstream(lib_dir / "module.py").close();
        return lib_dir;
    }

    // Create a directory containing a Python package (subdir with __init__.py)
    auto create_python_package_dir(const std::string& dir_name = "python_lib",
                                   const std::string& package_name = "mypackage") -> std::filesystem::path {
        auto lib_dir = path_ / dir_name;
        auto pkg_dir = lib_dir / package_name;
        std::filesystem::create_directories(pkg_dir);
        std::ofstream(pkg_dir / "__init__.py").close();
        return lib_dir;
    }

    TempDir(const TempDir&) = delete;
    TempDir& operator=(const TempDir&) = delete;

private:
    std::filesystem::path path_;
    static inline int counter_ = 0;
};

}  // namespace test_utils
