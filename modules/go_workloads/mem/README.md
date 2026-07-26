# Go memory workloads — reading the profile

Two archetypes. Run one with:

```bash
bazel run //tools/profile -- //modules/go_workloads:mem_retained_growth
```

Every run prints four buckets per frame and five derived ratios. See
[the C++ workloads](../../cpp_workloads/mem/README.md) for what each bucket and
ratio means and for a third archetype (fragmentation) that Go has no equivalent of
— its numbers are also exact, which makes them the better reference.

Go's figures are **sampled estimates**, so they move between runs; the ones below
are illustrative, not reproducible.

## What is different about Go

- **Both views come free.** Go's heap profile carries all four buckets in one
  artifact — no other language here does.
- **It samples.** `runtime.MemProfileRate` takes one sample per 32 KiB (set in
  `prof_dump.go`, matching the Rust shim's `lg_prof_sample:15`), and the runtime
  scales sampled values back up. The default 512 KiB is far too coarse: it reports
  the churn workload's live heap as pure noise.
- **`precision` is printed for every run** — effective live-sample count and the
  resulting error bar, roughly `1/sqrt(n)`. Read it before trusting `inuse_*`.
  Accuracy comes from the *number of samples*, not object size: 2,000 samples of
  1 KiB objects is good to ~2% even though no single object is likely to be sampled.
- **The leaf is your function, not the allocator.** Go strips runtime frames from
  heap stacks, so `top by self weight` is not comparable with C++, where the leaf
  is `__libcpp_allocate`.

## `mem_retained_growth` — a retention problem

```
turnover     1.00x        mean alloc  1,038 B      freed  0
mean live    1,038 B      live / RSS  95.7%
precision    ~2,100 live samples, ±2%
```

`Grow` retains every chunk it allocates: turnover 1, nothing freed, 96% of RSS is
live data. Allocation rate is not the problem — retention is. Note the tight error
bar: 68,711 estimated objects rest on ~2,100 real samples.

## `mem_string_churn` — an allocation-rate problem

```
Concat        7,794 allocs / 537,422,276 B     1 live / 133,517 B
turnover      1,343.80x    mean alloc  49,095 B     freed  7,793
live / RSS    4.9%         precision   ~12 live samples, ±29%
```

`Concat` uses `acc += piece`, so each round allocates a fresh string and copies the
whole accumulator: ~512 MB allocated to retain 128 KB. The fix is
`strings.Builder` or a preallocated capacity — and the profile shows it in one
line, with the cumulative and live columns side by side on the same frame.

Two cautions this workload exists to teach:

- **±29%.** The live heap is one object, so the estimate rests on a handful of
  samples. The magnitude is right; the digits are not. Contrast with
  `retained_growth` above.
- **The live object must be kept alive.** `main` uses only `len(s)` after the dump,
  so without the explicit `runtime.KeepAlive(s)` the compiler drops the reference
  and the GC inside the dump collects the very string the workload exists to show —
  reporting `Concat` as **0 live bytes** while still showing its 537 MB of
  allocation. If you write a new mem workload, hold its result across the dump.

## Aggregate means can mislead

`mean live` above reads ~127 B, not 128 KB: the aggregate is dominated by a few
thousand small runtime allocations that are also live. The ratio is honest but
coarse — when one frame dominates, read its row rather than the total.
