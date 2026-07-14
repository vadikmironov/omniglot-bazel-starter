#pragma once

#include <cstddef>
#include <cstdint>
#include <span>
#include <vector>

namespace cpp_workloads {

auto random_slice(std::size_t n, std::uint64_t seed) -> std::vector<std::uint64_t>;

// In-place recursive quicksort; the recursion gives the flamegraph its
// quicksort → partition tower.
void quicksort(std::span<std::uint64_t> v);

}  // namespace cpp_workloads
