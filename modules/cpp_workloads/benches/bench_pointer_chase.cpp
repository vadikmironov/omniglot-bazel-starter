// Pointer-chase bench: serially dependent random loads (memory-latency
// bound) against a contiguous sum of the same buffer (bandwidth bound).

#include <benchmark/benchmark.h>

#include <cstddef>

#include "pointer_chase.h"
#include "workload_n.h"

namespace {

constexpr std::size_t CHASE_DEFAULT_N = std::size_t{1} << 22U;

void bm_chase(benchmark::State& state) {
    const auto perm = cpp_workloads::build_cycle(cpp_workloads::workload_n(CHASE_DEFAULT_N), 42);
    for (auto unused : state) {
        benchmark::DoNotOptimize(cpp_workloads::chase_sum(perm));
    }
}
BENCHMARK(bm_chase);

void bm_array_sum(benchmark::State& state) {
    const auto perm = cpp_workloads::build_cycle(cpp_workloads::workload_n(CHASE_DEFAULT_N), 42);
    for (auto unused : state) {
        benchmark::DoNotOptimize(cpp_workloads::array_sum(perm));
    }
}
BENCHMARK(bm_array_sum);

}  // namespace
