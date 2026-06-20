#pragma once

#include <string>

/// Resolves Python library path via Bazel runfiles.
/// Looks for the source directory within the runfiles tree (e.g., "_main/modules/python_lib/src").
auto get_python_lib_path_via_runfiles(char** argv, std::string_view runfiles_relative_path,
                                      std::string& abs_lib_path) -> bool;

/// Resolves Python library path via environment or relative paths.
///
/// Resolution order:
///   1. PYTHON_LIB_PATH environment variable (if set and valid)
///   2. <exe_dir>/../lib/python (standard Unix install layout)
///   3. <exe_dir>/python_lib (flat install layout)
///
/// A valid path must be a directory containing .py files or Python packages.
auto get_python_lib_path_via_env(char** argv, std::string& abs_lib_path) -> bool;
