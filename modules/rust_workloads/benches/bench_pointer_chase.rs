//! Pointer-chase bench: serially dependent random loads (memory-latency
//! bound) against a contiguous sum of the same buffer (bandwidth bound).

use std::hint::black_box;

use criterion::{Criterion, criterion_group, criterion_main};
use pprof::criterion::{Output, PProfProfiler};
use rust_workloads::{pointer_chase, workload_n};

const DEFAULT_N: usize = 1 << 22;

fn bench_pointer_chase(c: &mut Criterion) {
    let n = workload_n(DEFAULT_N);
    let perm = pointer_chase::build_cycle(n, 42);
    let mut group = c.benchmark_group("pointer_chase");
    group.bench_function("chase", |bench| {
        bench.iter(|| pointer_chase::chase_sum(black_box(&perm)));
    });
    group.bench_function("array_sum", |bench| {
        bench.iter(|| pointer_chase::array_sum(black_box(&perm)));
    });
    group.finish();
}

criterion_group! {
    name = benches;
    // 10 samples: one chase walk over the 32 MB cycle takes hundreds of ms, so
    // the default 100 samples cannot fit criterion's 5s measurement window.
    config = Criterion::default()
        .sample_size(10)
        .with_profiler(PProfProfiler::new(100, Output::Protobuf));
    targets = bench_pointer_chase
}
criterion_main!(benches);
