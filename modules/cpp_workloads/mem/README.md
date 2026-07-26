# C++ memory workloads — reading the profile

Three archetypes, three different memory pathologies. Run one with:

```bash
bazel run //tools/profile -- //modules/cpp_workloads:mem_retained_growth
```

Every run prints four buckets per frame and five derived ratios. tcmalloc records
**every** allocation, so C++ numbers are exact — the figures below reproduce.

## The four buckets

|  | count | bytes |
|---|---|---|
| **cumulative** | `alloc_objects` — allocator call frequency, the cost of `operator new` itself | `alloc_space` — allocation rate: page faults, arena growth, memcpy pressure |
| **live** | `inuse_objects` — how many objects the heap is holding | `inuse_space` — footprint: RSS, OOM risk, cache pressure |

Cost is not proportional to bytes. 10M × 16 B costs far more allocator CPU than
100 × 1 MB while moving 60× fewer bytes, so `alloc_objects` and `alloc_space`
point at different fixes.

## The five ratios

| Ratio | Reads as |
|---|---|
| `alloc_space / inuse_space` | **turnover** — ≫1 means transient garbage; ≈1 means you keep everything you allocate |
| `alloc_space / alloc_objects` | mean allocation size — whether to attack count or bytes |
| `inuse_space / inuse_objects` | mean live size — size-class waste and pointer density |
| `alloc_objects - inuse_objects` | objects freed — lifetime |
| `inuse_space / VmRSS` | **fragmentation** — how much of the memory you hold is actually live data |

## `mem_retained_growth` — a retention problem

```
turnover     1.00x        mean alloc  1,048 B      freed  0
mean live    1,048 B      live / RSS  90.8%
```

Everything allocated is still held: turnover is exactly 1 and nothing was freed.
The allocator is behaving — 91% of RSS is live data. **Tuning allocation rate here
would achieve nothing**; the only lever is retaining less. This is the shape of a
leak, a cache without a bound, or a legitimately large working set.

## `mem_string_churn` — an allocation-rate problem

```
turnover     4,000.75x    mean alloc  64,024 B     freed  7,998
mean live    128,008 B    live / RSS  1.7%
```

512 MB allocated to retain 128 KB. `concat` grows a string by reallocating and
copying the whole accumulator each round, so it allocates O(n²) bytes and keeps
one. Note **RSS peaked at ~9 MB**: high churn cost the allocator almost nothing in
footprint, because tcmalloc recycled the same pages 8,000 times.

The lesson pairs with the ratio above it — **turnover does not predict RSS**. This
workload has 2,000× the turnover of `mem_fragmentation` and a fraction of its
footprint waste. Optimise churn for CPU and GC pressure, not for memory size.

## `mem_fragmentation` — a fragmentation problem

```
turnover     2.00x        mean alloc  5,836 B      freed  50,001
mean live    8,745 B      live / RSS  62.2%
```

The one pathology no single bucket can show. Turnover is a mild 2× and 218 MB is
genuinely live — but **38% of RSS is not live data**. The workload allocates 50,000
blocks of 512–8191 B, frees every other one, then doubles the survivors: the freed
holes are too small for the enlarged blocks, so the allocator maps fresh pages and
keeps the old ones.

Two details worth noticing:

- **`mean live` (8,745 B) exceeds `mean alloc` (5,836 B).** The survivors are
  systematically larger than the average allocation — exactly right, since the ones
  kept are the ones that were doubled. No single column shows this.
- Only `inuse_space / VmRSS` identifies the problem. Both live bytes and turnover
  look unremarkable on their own.

## Reading it in practice

| Symptom | Bucket to look at |
|---|---|
| CPU sitting in `operator new` | `alloc_objects` |
| Throughput drops under load | `alloc_space` |
| OOM, container limits | `inuse_space` |
| Large heap, poor locality | `inuse_objects` (mean live size) |
| RSS far above live bytes | `inuse_space / VmRSS` |

The common fixes trade one bucket for another — pooling and arenas convert churn
into permanent footprint, dropping `alloc_space` while raising `inuse_space`. That
is why the runner prints both: with one view you cannot tell a fix from a
relocation of the cost.
