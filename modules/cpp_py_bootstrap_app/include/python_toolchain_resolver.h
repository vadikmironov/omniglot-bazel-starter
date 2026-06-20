#pragma once

#include <string>

/// Resolves Python toolchain path using Bazel runfiles.
/// Uses the relative interpreter path from rules_python to locate the Python home
/// directory in the runfiles tree.
auto get_python_toolchain_path_via_runfiles(char** argv, const std::string& rel_interpreter_path,
                                            std::string& abs_interpreter_path) -> bool;

/// Resolves Python toolchain path using environment variables.
/// Checks PYTHONHOME first, then searches PATH for python3/python interpreters.
auto get_python_toolchain_path_via_env(std::string& abs_interpreter_path) -> bool;
