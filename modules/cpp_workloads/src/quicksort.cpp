#include "quicksort.h"

#include <cstddef>
#include <cstdint>
#include <random>
#include <span>
#include <utility>
#include <vector>

namespace cpp_workloads {

namespace {

// Lomuto partition around the last element; returns the pivot's final slot.
auto partition(std::span<std::uint64_t> v) -> std::size_t {
    const std::uint64_t pivot = v[v.size() - 1];
    std::size_t store = 0;
    for (std::size_t i = 0; i < v.size() - 1; i++) {
        if (v[i] <= pivot) {
            std::swap(v[store], v[i]);
            store++;
        }
    }
    std::swap(v[store], v[v.size() - 1]);
    return store;
}

}  // namespace

auto random_slice(std::size_t n, std::uint64_t seed) -> std::vector<std::uint64_t> {
    std::mt19937_64 rng(seed);
    std::vector<std::uint64_t> v(n);
    for (auto& x : v) {
        x = rng();
    }
    return v;
}

void quicksort(std::span<std::uint64_t> v) {
    if (v.size() <= 1) {
        return;
    }
    const std::size_t mid = partition(v);
    quicksort(v.subspan(0, mid));
    quicksort(v.subspan(mid + 1));
}

}  // namespace cpp_workloads
