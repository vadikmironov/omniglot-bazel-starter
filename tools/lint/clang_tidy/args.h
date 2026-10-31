#pragma once

#include <string>
#include <string_view>
#include <vector>

namespace clang_tidy {

// Splits a clang config file into its args. Bazel writes the file one arg per
// line, in single quotes when the arg needs them, with each ' in it as '\''.
auto split_config(std::string_view text) -> std::vector<std::string>;

// Swaps GCC's own header directory, lib/gcc/<target>/<version>/include, for
// clang's in each -isystem, whether the path is in the same arg or the next.
auto with_clang_headers(const std::vector<std::string>& args,
                        std::string_view clang_headers)
    -> std::vector<std::string>;

}  // namespace clang_tidy
