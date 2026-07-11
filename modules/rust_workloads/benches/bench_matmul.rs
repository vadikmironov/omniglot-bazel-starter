//! Matrix-multiply bench: the `ijk` vs `ikj` loop-order gap is cache
//! behaviour — in-process profiles show a hot loop, an external sampler's
//! cache counters explain the difference.

use std::hint::black_box;

use criterion::{Criterion, criterion_group, criterion_main};
use pprof::criterion::{Output, PProfProfiler};
use rust_workloads::{matmul, workload_n};

const DEFAULT_N: usize = 256;

fn bench_matmul(c: &mut Criterion) {
    let n = workload_n(DEFAULT_N);
    let a = matmul::random_matrix(n, 42);
    let b = matmul::random_matrix(n, 43);
    let mut group = c.benchmark_group("matmul");
    group.bench_function("ijk", |bench| {
        bench.iter(|| matmul::multiply_ijk(black_box(&a), black_box(&b), n));
    });
    group.bench_function("ikj", |bench| {
        bench.iter(|| matmul::multiply_ikj(black_box(&a), black_box(&b), n));
    });
    group.finish();
}

criterion_group! {
    name = benches;
    config = Criterion::default().with_profiler(PProfProfiler::new(100, Output::Protobuf));
    targets = bench_matmul
}
criterion_main!(benches);
