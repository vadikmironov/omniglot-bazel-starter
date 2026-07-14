// Matrix-multiply bench: the ijk vs ikj loop-order gap is cache
// behaviour — in-process profiles show a hot loop, an external
// sampler's cache counters explain the difference.

#include <benchmark/benchmark.h>

#include <cstddef>

#include "matmul.h"
#include "workload_n.h"

namespace {

constexpr std::size_t MATMUL_DEFAULT_N = 256;

void bm_matmul_ijk(benchmark::State& state) {
    const std::size_t n = cpp_workloads::workload_n(MATMUL_DEFAULT_N);
    const auto a = cpp_workloads::random_matrix(n, 42);
    const auto b = cpp_workloads::random_matrix(n, 43);
    for (auto unused : state) {
        benchmark::DoNotOptimize(cpp_workloads::multiply_ijk(a, b, n));
    }
}
BENCHMARK(bm_matmul_ijk);

void bm_matmul_ikj(benchmark::State& state) {
    const std::size_t n = cpp_workloads::workload_n(MATMUL_DEFAULT_N);
    const auto a = cpp_workloads::random_matrix(n, 42);
    const auto b = cpp_workloads::random_matrix(n, 43);
    for (auto unused : state) {
        benchmark::DoNotOptimize(cpp_workloads::multiply_ikj(a, b, n));
    }
}
BENCHMARK(bm_matmul_ikj);

}  // namespace
