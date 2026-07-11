//! Quicksort bench: recursive call tree renders as a `quicksort → partition`
//! flamegraph tower, with a branch-miss story on random input.

use std::hint::black_box;

use criterion::{BatchSize, Criterion, criterion_group, criterion_main};
use pprof::criterion::{Output, PProfProfiler};
use rust_workloads::{quicksort, workload_n};

const DEFAULT_N: usize = 1_000_000;

fn bench_quicksort(c: &mut Criterion) {
    let n = workload_n(DEFAULT_N);
    let input = quicksort::random_vec(n, 42);
    c.bench_function("quicksort", |bench| {
        bench.iter_batched_ref(
            || input.clone(),
            |v| quicksort::quicksort(black_box(v)),
            BatchSize::LargeInput,
        );
    });
}

criterion_group! {
    name = benches;
    // 10 samples: one iteration sorts 1M elements, so the default 100 samples
    // cannot fit criterion's 5s measurement window.
    config = Criterion::default()
        .sample_size(10)
        .with_profiler(PProfProfiler::new(100, Output::Protobuf));
    targets = bench_quicksort
}
criterion_main!(benches);
