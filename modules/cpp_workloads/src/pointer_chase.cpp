#include "pointer_chase.h"

#include <cstddef>
#include <cstdint>
#include <numeric>
#include <random>
#include <utility>
#include <vector>

namespace cpp_workloads {

auto build_cycle(std::size_t n, std::uint64_t seed) -> std::vector<std::size_t> {
    std::mt19937_64 rng(seed);
    std::vector<std::size_t> perm(n);
    std::iota(perm.begin(), perm.end(), std::size_t{0});
    if (n < 2) {
        // No cycle to build — and n - 1 below would wrap at n == 0.
        return perm;
    }
    for (std::size_t i = n - 1; i >= 1; i--) {
        std::uniform_int_distribution<std::size_t> dist(0, i - 1);
        std::swap(perm[i], perm[dist(rng)]);
    }
    return perm;
}

auto chase_sum(const std::vector<std::size_t>& perm) -> std::size_t {
    std::size_t idx = 0;
    std::size_t acc = 0;
    for (std::size_t step = 0; step < perm.size(); step++) {
        acc += idx;
        idx = perm[idx];
    }
    return acc;
}

auto array_sum(const std::vector<std::size_t>& perm) -> std::size_t {
    std::size_t acc = 0;
    for (const auto v : perm) {
        acc += v;
    }
    return acc;
}

}  // namespace cpp_workloads
