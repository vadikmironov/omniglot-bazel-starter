#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

namespace cpp_workloads {

// Single-cycle permutation of 0..n (Sattolo's algorithm): following
// i = perm[i] from any start visits every slot exactly once.
auto build_cycle(std::size_t n, std::uint64_t seed) -> std::vector<std::size_t>;

// Walks the cycle once from slot 0, summing the visited indices.
auto chase_sum(const std::vector<std::size_t>& perm) -> std::size_t;

// The streaming counterpart: a contiguous sum of the buffer.
auto array_sum(const std::vector<std::size_t>& perm) -> std::size_t;

}  // namespace cpp_workloads
