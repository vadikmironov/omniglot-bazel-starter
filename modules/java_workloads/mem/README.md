# Java memory workloads — reading the profile

Two archetypes. Run one with:

```bash
bazel run //tools/profile -- //modules/java_workloads:mem_retained_growth
```

See [the C++ workloads](../../cpp_workloads/mem/README.md) for what the four buckets
and five ratios mean — C++ measures all of them exactly, which makes it the reference.

**Java fills one of the four buckets.** The others are not "not implemented yet"; the
data does not exist in JFR. Everything below was verified against JDK 17/21 and
`jfr-converter` 4.5.

## What you get

```
     alloc_objects     alloc_space   inuse_objects     inuse_space  frame
                 —        66519160               —               —  byte[]_[k]

  turnover     (alloc_space / inuse_space)        —
  mean alloc   (alloc_space / alloc_objects)      —
  mean live    (inuse_space / inuse_objects)      —
  freed        (alloc_objects - inuse_objects)    —
  live / RSS   (heap live / VmRSS)                36.2%
  heap live    (whole heap, not attributed)       78,594,672 B (75.0 MiB)
  precision    (throttled @ 300 events/s)         byte weights honest, object counts are not
```

The flamegraph is titled **"(heap, allocated)"**, not "live" — Java is the only language
here whose memory profile measures allocation rather than retention.

## Why `alloc_objects` is unavailable

`jdk.ObjectAllocationSample` is *throttled* sampling: it emits at most N events per
second, each weighted with the bytes it represents. The event count reflects the
throttle, not the program — both workloads below produce exactly **200 events** despite
allocating 67 MB and 512 MB respectively. There is no object count to recover, in any
JDK version.

**Read `alloc_space` as relative, not absolute.** The weights are an estimate, and
throttling degrades it badly once the allocation rate outruns the sample budget:

| Workload | true allocation | JFR `alloc_space` |
|---|---|---|
| `mem_retained_growth` | 67,108,864 | ~66.5 MB — close |
| `mem_string_churn` | ~512,000,000 | **87.4 MB — ~6× under** |

So the *ranking* of call sites is trustworthy and the absolute totals are not. C++ and
Python measure the same workloads exactly (512,127,976 and 512,383,851 respectively) if
you need the real number.

## Why `inuse_space` and `inuse_objects` are unavailable

JFR has a live-object event, `jdk.OldObjectSample`, and the shim could enable it. Two
independent reasons it cannot fill these columns:

1. **It carries no size.** Its complete field set is `allocationTime`, `objectAge`,
   `lastKnownHeapUsage`, `object{address, type, description, referrer}`, `arrayElements`,
   `root`, `stackTrace`. `lastKnownHeapUsage` is the whole heap at sample time, not the
   object's footprint. There is no per-object byte figure to sum.
2. **Its yield collapses on churn.** It is a leak sampler over a bounded queue
   (`old-object-queue-size`, default 256) holding objects that survived a GC:

   | Workload | `jdk.OldObjectSample` events |
   |---|---|
   | `mem_retained_growth` | 47 |
   | `mem_string_churn` | **1** |

   So it would be least informative in exactly the comparison you would want it for.

`jfrconv --live` does not help either: its `LiveObject` type binds to the event name
`profiler.LiveObject`, emitted by async-profiler's *native agent*. The string `OldObject`
does not appear anywhere in the converter jar, so it cannot read JDK recordings' live
events at any settings.

## Where the live figure does come from

`heap live` is `MemoryMXBean.getHeapMemoryUsage().getUsed()` read after `System.gc()` —
**exact**, but whole-process: it includes JVM and JFR overhead and is not attributed to
call sites. That is why it appears on its own line and drives only `live / RSS`, and why
it is *not* used as the `turnover` denominator. Mixing it with the attributed
`alloc_space` column would compare a workload's allocation against the entire runtime's
retention. For `mem_string_churn` the gap is stark: the workload retains 128,000 bytes of
payload inside a ~10 MB live heap.

## The two workloads

- **`mem_retained_growth`** — retains every chunk it allocates. `alloc_space` ≈ 66.5 MB
  against 67,108,864 bytes of payload; the difference is JFR's weighting, not error.
- **`mem_string_churn`** — allocates ~512 MB to retain 128,000 bytes. `alloc_space` shows
  the churn plainly, which is Java's strength here. The retention side is invisible, so
  compare against C++ or Python for the live half of the story.

## If you need a real live heap by call site

The only route is async-profiler's **native agent** (`-e alloc --live`), which emits the
`profiler.LiveObject` events `jfrconv --live` expects. It is deliberately not wired here:
it ships a per-platform `.so` and would break the hermetic-toolchain rule the rest of the
profiling feature holds to.

An exact live heap *by class* — no stacks — is available and cheap:
`jdk.ObjectCountAfterGC` carries `count` and `totalSize` per class after each GC. It is a
census rather than a sample, so it is honest, but it attributes on a different axis than
every other language's report, so it is not wired either.
