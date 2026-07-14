#pragma once

#include <cstddef>
#include <string>
#include <string_view>

namespace cpp_workloads {

// O(n²) string concatenation: every round allocates a fresh string and
// copies the whole accumulator — high transient allocation rate, tiny
// live heap at any instant.
auto concat(std::size_t pieces, std::string_view piece) -> std::string;

}  // namespace cpp_workloads
