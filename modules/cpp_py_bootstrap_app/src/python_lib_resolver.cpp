#include "python_lib_resolver.h"

#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <memory>
#include <string>
#include <string_view>
#include <vector>

#include "tools/cpp/runfiles/runfiles.h"

namespace {

/// Checks for .py files or directories with __init__.py.
auto is_valid_python_lib_path(const std::filesystem::path& path) -> bool {
    if (!std::filesystem::is_directory(path)) {
        return false;
    }

    return std::ranges::any_of(std::filesystem::directory_iterator(path), [](const auto& entry) -> bool {
        if (entry.is_regular_file() && entry.path().extension() == ".py") {
            return true;
        }
        return entry.is_directory() && std::filesystem::exists(entry.path() / "__init__.py");
    });
}

}  // namespace

auto get_python_lib_path_via_runfiles(char** argv, std::string_view runfiles_relative_path,
                                      std::string& abs_lib_path) -> bool {
    using bazel::tools::cpp::runfiles::Runfiles;

    std::string error = std::string();
    std::unique_ptr<Runfiles> runfiles(Runfiles::Create(argv[0], &error));  // NOLINT(cppcoreguidelines-pro-bounds-pointer-arithmetic)
    if (!runfiles) {
        return false;
    }

    abs_lib_path = runfiles->Rlocation(std::string(runfiles_relative_path));
    return !abs_lib_path.empty() && is_valid_python_lib_path(abs_lib_path);
}

auto get_python_lib_path_via_env(char** argv, std::string& abs_lib_path) -> bool {
    if (const char* lib_path = std::getenv("PYTHON_LIB_PATH"); lib_path != nullptr) {  // NOLINT(concurrency-mt-unsafe)
        std::filesystem::path const env_path(lib_path);
        if (is_valid_python_lib_path(env_path)) {
            abs_lib_path = env_path.string();
            return true;
        }
    }

    std::filesystem::path const exe_path(argv[0]);  // NOLINT(cppcoreguidelines-pro-bounds-pointer-arithmetic)
    std::filesystem::path const exe_dir = exe_path.parent_path();

    // Common installation layouts to check
    std::vector<std::filesystem::path> const candidate_paths = {
        // Standard Unix-style installation: <prefix>/bin/exe -> <prefix>/lib/python
        exe_dir / ".." / "lib" / "python",
        // Flat installation layout: exe and python_lib in same directory
        exe_dir / "python_lib",
        // Share directory layout: <prefix>/bin/exe -> <prefix>/share/<app>/python
        exe_dir / ".." / "share" / "cpp_py_bootstrap_app" / "python",
    };

    for (const auto& candidate : candidate_paths) {
        if (is_valid_python_lib_path(candidate)) {
            abs_lib_path = std::filesystem::canonical(candidate).string();
            return true;
        }
    }

    return false;
}
