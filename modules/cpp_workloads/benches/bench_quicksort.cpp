// Quicksort bench: recursive call tree renders as a quicksort →
// partition flamegraph tower, with a branch-miss story on random input.

#include <benchmark/benchmark.h>

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <vector>

#include "quicksort.h"
#include "workload_n.h"

namespace {

constexpr std::size_t QUICKSORT_DEFAULT_N = 1'000'000;

void bm_quicksort(benchmark::State& state) {
    const std::size_t n = cpp_workloads::workload_n(QUICKSORT_DEFAULT_N);
    const auto input = cpp_workloads::random_slice(n, 42);
    std::vector<std::uint64_t> buf(n);
    for (auto unused : state) {
        std::ranges::copy(input, buf.begin());
        cpp_workloads::quicksort(buf);
        benchmark::DoNotOptimize(buf.data());
    }
}
BENCHMARK(bm_quicksort);

}  // namespace
