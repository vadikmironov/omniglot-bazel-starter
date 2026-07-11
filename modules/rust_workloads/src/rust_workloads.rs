//! Profiling workloads: deterministic, size-tunable kernels with distinct
//! CPU and memory signatures, exercised by the `bench_*` and `mem_*` targets.

pub mod fragmentation;
pub mod matmul;
pub mod pointer_chase;
pub mod quicksort;
pub mod retained_growth;
pub mod string_churn;

/// Workload size from `WORKLOAD_N`, falling back to the target's default.
pub fn workload_n(default: usize) -> usize {
    std::env::var("WORKLOAD_N")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}
