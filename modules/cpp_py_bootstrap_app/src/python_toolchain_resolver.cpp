#include "python_toolchain_resolver.h"

#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <memory>
#include <string>
#include <string_view>
#include <system_error>
#include <vector>

#include "tools/cpp/runfiles/runfiles.h"

namespace {

/// Checks whether python_home contains a Python standard library.
/// Version-agnostic: scans for any pythonX.Y directory containing os.py.
auto has_python_stdlib(const std::filesystem::path& python_home) -> bool {
#ifdef _WIN32
    // Windows: <home>/Lib/os.py (capital L, no version subdirectory)
    return std::filesystem::exists(python_home / "Lib" / "os.py");
#else
    // Unix/macOS: <home>/lib/pythonX.Y/os.py
    auto lib_dir = python_home / "lib";
    if (!std::filesystem::is_directory(lib_dir)) {
        return false;
    }
    std::error_code ec;  // NOLINT(readability-identifier-length)
    return std::ranges::any_of(std::filesystem::directory_iterator(lib_dir, ec), [](const auto& entry) -> bool {
        if (!entry.is_directory()) {
            return false;
        }
        const auto dirname = entry.path().filename().string();
        return dirname.starts_with("python") && std::filesystem::exists(entry.path() / "os.py");
    });
#endif
}

}  // namespace

auto get_python_toolchain_path_via_runfiles(char** argv, const std::string& rel_interpreter_path,
                                            std::string& abs_interpreter_path) -> bool {
    using bazel::tools::cpp::runfiles::Runfiles;

    // Bazel runfiles paths always use forward slashes regardless of platform
    std::string const prefix = std::string("../");
    std::string const suffix = std::string("/bin/python3");
    auto interpreter_path_view = std::string_view(rel_interpreter_path);
    if (interpreter_path_view.find(prefix) != std::string_view::npos) {
        interpreter_path_view = interpreter_path_view.substr(prefix.size(), interpreter_path_view.size());
    }
    if (interpreter_path_view.find(suffix) != std::string_view::npos) {
        interpreter_path_view = interpreter_path_view.substr(0, interpreter_path_view.size() - suffix.size());
    }

    std::string error = std::string();
    std::unique_ptr<Runfiles> runfiles(Runfiles::Create(argv[0], &error));  // NOLINT(cppcoreguidelines-pro-bounds-pointer-arithmetic)
    if (not runfiles) {
        return false;
    }

    abs_interpreter_path = runfiles->Rlocation(std::string(interpreter_path_view));
    return !abs_interpreter_path.empty() && std::filesystem::is_directory(abs_interpreter_path);
}

auto get_python_toolchain_path_via_env(std::string& abs_interpreter_path) -> bool {
    if (const char* pythonhome = std::getenv("PYTHONHOME"); pythonhome != nullptr) {  // NOLINT(concurrency-mt-unsafe)
        std::filesystem::path const home_path(pythonhome);
        if (has_python_stdlib(home_path)) {
            abs_interpreter_path = home_path.string();
            return true;
        }
        // PYTHONHOME is set but doesn't contain a valid Python stdlib —
        // fall through to PATH search (user may have PYTHONHOME set for
        // a different purpose, e.g. a virtualenv wrapper).
    }

    const char* path_env = std::getenv("PATH");  // NOLINT(concurrency-mt-unsafe)
    if (path_env == nullptr) {
        return false;
    }

    std::vector<std::string> const interpreters = {"python3", "python"};
#ifdef _WIN32
    const char path_separator = ';';
    for (auto& interp : interpreters) {
        interp += ".exe";
    }
#else
    const char path_separator = ':';
#endif

    std::string const path_str(path_env);
    std::string::size_type start = 0;
    std::string::size_type end = 0;

    while ((end = path_str.find(path_separator, start)) != std::string::npos || start < path_str.size()) {
        if (end == std::string::npos) {
            end = path_str.size();
        }

        std::filesystem::path const dir(path_str.substr(start, end - start));
        for (const auto& interp : interpreters) {
            std::filesystem::path const candidate = dir / interp;
            if (std::filesystem::exists(candidate) && std::filesystem::is_regular_file(candidate)) {
                // Resolve symlinks (e.g. Homebrew, pyenv) to find the real installation
                std::error_code resolve_ec;
                std::filesystem::path resolved = std::filesystem::canonical(candidate, resolve_ec);
                if (resolve_ec) {
                    resolved = candidate;  // canonical() failed — use original path
                }

#ifdef _WIN32
                // Windows: python.exe lives at <prefix>/python.exe (no bin/ subdirectory)
                std::filesystem::path python_home = resolved.parent_path();
#else
                // Unix/macOS: python3 lives at <prefix>/bin/python3
                std::filesystem::path const python_home = resolved.parent_path().parent_path();
#endif
                if (has_python_stdlib(python_home)) {
                    abs_interpreter_path = python_home.string();
                    return true;
                }
            }
        }

        start = end + 1;
        if (start > path_str.size()) {
            break;
        }
    }

    return false;
}
