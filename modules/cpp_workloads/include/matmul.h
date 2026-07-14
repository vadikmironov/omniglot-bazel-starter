#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

namespace cpp_workloads {

// Row-major n×n matrix filled from a seeded PRNG.
auto random_matrix(std::size_t n, std::uint64_t seed) -> std::vector<double>;

// Dense n×n matrix multiply in two loop orders: ijk strides column-wise
// through b (cache-hostile), ikj streams both operands row-major.
auto multiply_ijk(const std::vector<double>& a, const std::vector<double>& b, std::size_t n)
    -> std::vector<double>;
auto multiply_ikj(const std::vector<double>& a, const std::vector<double>& b, std::size_t n)
    -> std::vector<double>;

}  // namespace cpp_workloads
