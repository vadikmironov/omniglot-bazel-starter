# Rust memory workloads — reading the profile

Three archetypes. Run one with:

```bash
bazel run //tools/profile -- //modules/rust_workloads:mem_retained_growth
```

See [the C++ workloads](../../cpp_workloads/mem/README.md) for what the four buckets
and five ratios mean. Rust uses the **same capture mechanism as C++** — gperftools'
tcmalloc heap profiler — so its numbers are exact and directly comparable.

## Why tcmalloc and not jemalloc

The workloads link `@gperftools//:tcmalloc` (via `link_deps`, since rules_rust
deprecates C++ libraries in `deps`). Linking is the whole integration: tcmalloc
interposes `malloc`/`free`, so Rust's allocations are captured **without a
`#[global_allocator]`**, and the shim just drives `HeapProfilerStart/Dump/Stop`
over FFI.

The predecessor was jemalloc via `jemalloc_pprof`, which could only ever report
**live bytes** — one of the four buckets. jemalloc removed `opt.prof_accum` in
5.0.0 because cumulative counts oblige it to retain every unique backtrace for the
whole run, so `alloc_*` was permanently out of reach. tcmalloc accepts that cost
and reports both halves. Switching also dropped three upstream warts: Linux-only
capture, a stack-tail trimming workaround for jemalloc's own
`_rjem_je_prof_backtrace` frames, and a tokio mutex pulled in for a one-shot dump.

**Trade-off worth knowing:** Rust and C++ now demonstrate the same allocator, so
the fragmentation workload tells tcmalloc's story in both. You gain exact
comparability and lose one allocator's worth of coverage.

**Consequence for scaffolds:** Rust memory profiling now depends on the C++ shard
(gperftools, the pprof CLI, llvm-symbolizer), so it is gated on `lang:cpp`. A
Rust-only scaffold keeps CPU profiling and has no memory capture.

## Measured

Figures from real runs; tcmalloc records every allocation, so they reproduce.

| Workload | turnover | mean alloc | mean live | `inuse_space` |
|---|---|---|---|---|
| `mem_retained_growth` | 1.00× | 1,048 B | 1,048 B | **68,681,728** |
| `mem_fragmentation` | 2.00× | 5,803 B | 8,715 B | 216,689,436 |
| `mem_string_churn` | 5,996× | 95,982 B | 85,384 B | 255,968 |

`mem_retained_growth` reports **68,681,728 bytes — byte-identical to C++**, because
the shapes are identical: 65,536 × 1024 B chunks plus 65,536 × 24 B for the outer
`Vec`'s pointer/len/cap triples. `mem_fragmentation` matches C++'s 2.00× turnover
and its mean-live-exceeds-mean-alloc signature (the survivors are the resized
blocks).

**`mem_string_churn` diverges from C++ on purpose.** Rust's `String` grows
geometrically through `RawVec::finish_grow` rather than reallocating to exact size,
so it allocates ~1.5 GB where C++'s `std::string` allocates ~512 MB, and the leaf
is `RawVecInner::finish_grow` rather than the workload function. Same O(n²)
pathology, different amplification — a genuine cross-language finding rather than a
measurement artefact.

## Reading the leaf frames

Rust's stacks come through demangled (`rust_workloads::retained_growth::grow`,
`std::rt::lang_start::{{closure}}`) via llvm-symbolizer, and carry no allocator
machinery — unlike jemalloc's dumps, which needed the tail stripped. Generic and
inlined frames surface as their monomorphised names, so `finish_grow` and
`SpecFromIterNested::from_iter` appear where the standard library did the
allocating on the workload's behalf.
