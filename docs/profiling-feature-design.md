# `feature:profiling` — design

> Status: **scoping complete, not yet implemented.** Second composable feature after
> `feature:coverage`, same `feature:` bootstrap-segment model. Local design notes —
> not user-facing product docs.

## Goal

Add cross-language **CPU and memory profiling** to the polyglot starter, driven by
dedicated benchmark targets, rendered to flamegraphs. The same composable-segment
approach as coverage: per-language capture feeds one shared renderer.

Languages: C, C++, Go, Java, Python, Rust.

## Locked decisions

| Decision | Choice |
|---|---|
| Scope | **Both CPU and memory** profiling |
| Workload | **Dedicated benchmark targets** (profiling has no free spine like coverage's test suite — it needs something running to measure) |
| Workload hosting | **Split by kind.** CPU benches live in the idiomatic bench frameworks. **Memory workloads are plain one-shot binaries** the runner executes once under the profiler — bench frameworks calibrate and re-run the body N times, which contaminates leak / heap-over-time workloads (growth scales with iteration count) and mangles the heap-over-time curve. Bonus: shrinks the JMH / pytest-benchmark integration surface to CPU only |
| Bench frameworks (CPU) | **Idiomatic per language**: Go `testing.B`, Rust criterion, C++ google/benchmark (also hosts the C benches — the harness is C++, the workload code stays C), Java JMH, Python pytest-benchmark |
| Posture | **Local / on-demand only** — no CI job, no gating (perf numbers are too noisy on CI runners) |
| Capture | **Dual** — in-process/hermetic default + non-hermetic system-sampling opt-in (see below) |
| Renderer | **inferno** (`rules_rust`) — the Rust rewrite of `flamegraph.pl`; builds hermetically through the existing Rust toolchain |

## Architecture

**Spine (mirrors coverage's LCOV → genhtml):** per-language capture → **collapsed / folded
stacks** → **`inferno-flamegraph` → SVG**. `pprof` stays a richer *secondary* view (interactive
callgraph / web UI) for the languages that speak it natively (Go, and C++/Rust via
gperftools / pprof-rs).

**Interchange model — pprof protobuf is the inner lingua franca.** Every capture tool that can
emit pprof does: Go CPU/heap, pprof-rs (Rust CPU), gperftools CPU/heap (C/C++), and Rust heap via
`jemalloc_pprof`. One hermetic converter — `felixge/pprofutils` (`pprof2folded`, pure Go, builds
with the existing rules_go toolchain) — turns all of them into folded stacks. Bespoke conversions
remain for only two languages:

- **Java:** JFR → collapsed via async-profiler's converter, a **pure-Java jar on Maven Central**
  (`tools.profiler:jfr-converter`, 4.x — the pre-4.0 name was `async-profiler-converter`). Slots
  straight into the existing `maven.install`; fully hermetic, no binary downloads.
- **Python:** two small in-repo adapters — pyinstrument → folded (~20-line custom renderer on its
  documented Session/Frame API; it records true stacks) and memray → folded (~30-line adapter on
  its documented reader API; memray's built-in `transform` targets gprof2dot/csv, not folded).

### Capture is dual

- **Default — in-process / hermetic.** Privilege-free, no `perf`/root/`ptrace`, cross-platform,
  matches the hermetic-toolchain ethos. Requires instrumenting each bench binary.
- **Opt-in — non-hermetic system sampling.** `perf` on Linux, `dtrace` on macOS. Uses host tools
  (not Bazel-provided), needs privileges (`perf_event_paranoid` / `ptrace`), platform-specific. No
  code instrumentation; sees kernel / syscall / off-CPU frames the in-process path cannot. Exposed
  as a runner mode / `--config`, with documented prerequisites.

  Synergy with the renderer: inferno ships `inferno-collapse-perf` and `inferno-collapse-dtrace`,
  so both external samplers feed the same renderer with **zero extra converters**.
  (`perf` = Linux, `dtrace` = macOS/BSD; the Linux dtrace port is fringe and out of scope.)

### Per-language in-process tool matrix

All privilege-free, everything reaches pprof or collapsed stacks → inferno.

| Lang | Bench framework (CPU) | CPU | Memory | interchange |
|---|---|---|---|---|
| Go | `testing.B` | `runtime/pprof` | heap pprof | pprof |
| Rust | criterion | `pprof-rs` | `tikv-jemallocator` (profiling feature) + `jemalloc_pprof` | pprof |
| C++ / C | google/benchmark | gperftools* | gperftools heap* | pprof |
| Python | pytest-benchmark | `pyinstrument` | `memray` | folded via small adapters (see interchange model) |
| Java | JMH | JFR | JFR alloc | JFR → collapsed via `tools.profiler:jfr-converter` |

\* C++ is the one that needs a Bazel-packaging probe — gperftools isn't cleanly in BCR.

Two capture choices changed during review, both for hub convergence with maintained tools:

- **Rust memory: `dhat` → jemalloc.** dhat-rs emits DHAT-viewer JSON — a format island that never
  reaches pprof or folded. `jemalloc_pprof` (actively maintained, ~10M downloads) converts jemalloc
  heap profiles to pprof protobuf in-process; capture is `tikv-jemallocator` with the `profiling`
  feature + `MALLOC_CONF`.
- **Python CPU: `cProfile` → `pyinstrument`.** cProfile records caller→callee edges, not full
  stacks — folded output from it is a reconstruction, and the known converter (`flameprof`) is
  unmaintained. pyinstrument is a maintained, in-process, pip-hermetic statistical sampler that
  records true stacks (also resolving the tracing-overhead distortion).

## Benchmark workloads

Chosen via a weighted scored comparison. The headline criterion is **profiler↔in-process
contrast** (weighted ×2) — does the workload reveal something the *system* profiler
(`perf` / `dtrace` / `massif`) shows that an in-process profiler cannot? — because that contrast
is the whole reason the non-hermetic path exists.

**Key finding:** no single workload maximizes every aspect. For CPU, flamegraph legibility and
hardware-counter contrast pull in *opposite* directions (cache/branch workloads have flat
flamegraphs; recursive workloads have rich flamegraphs but dull counters). So a **covering set**
beats any single workload.

### CPU / performance set — all 6 languages

| Workload | What it teaches |
|---|---|
| **Matrix multiply (ijk vs ikj)** | Cache behaviour / `LLC-load-misses` — the perf-vs-in-process showcase. In-process says "the loop is hot"; only `perf` explains the 5–10× loop-order gap. Real-world GEMM. |
| **Quicksort (random input)** | The one rich recursive flamegraph (`sort → partition`) **plus** a `branch-misses` story. |
| **Pointer-chase vs array sum** | `stalled-cycles` / memory-latency bound; bridges to memory layout. |

Together: cache + branch + latency counters, plus one structured flamegraph.

*Rejected:* recursive Fibonacci (iconic flamegraph but zero perf contrast), matrix traversal
row/col and branchy binary search (subsumed by the above).

### Memory set

The memory analog of the contrast axis is **external tools (`valgrind massif`, `heaptrack`,
RSS-over-time) vs in-process alloc-site profilers**.

| Workload | Languages | What it teaches |
|---|---|---|
| **Unbounded retained growth (logical leak)** | all 6 | The live-heap teacher: massif's heap-over-time curve vs in-process *where-allocated* attribution. Portable — a "reachable-but-unused" leak works in GC languages too. |
| **String-concat O(n²) churn** | all 6 | Allocation-*rate* / transient churn that in-process alloc profilers reveal but RSS/peak snapshots miss — the mirror image of the leak. |
| **Fragmentation** (free every other, realloc larger) | C / C++ / Rust only | RSS stays high while live bytes drop — the external↔in-process poster child. Reproduces only on manual allocators; GC languages compact/manage the heap. |

*Rejected as everywhere-workloads:* word-count / tree-build / batch-pipeline (portable but low
external contrast). Word-count is the fallback if a fully-portable third is ever wanted.

**Hosting:** memory workloads are **one-shot binaries**, not framework benches (see locked
decisions) — iteration/calibration loops contaminate leak and heap-over-time behaviour.

**Allocator sensitivity (→ README):** the fragmentation story depends on which allocator the
binary links. Rust memory benches link jemalloc (required for `jemalloc_pprof`); C/C++ links
tcmalloc when gperftools' heap profiler is active (the profiler lives in tcmalloc) and glibc
malloc otherwise. Each language's README entry must state whose allocator story it tells.

### Workload quality bar

Every implementation must be: identical & idiomatic across languages, **stdlib-only** (no library
that would dominate the profile), deterministic (seeded, no I/O), tunable by a size `N`, and
resistant to being optimized away (read `N` at runtime, pass results through the bench framework's
`black_box`).

**Full matrix:** 3 CPU + 2 memory across all 6 languages, + fragmentation on C/C++/Rust =
**33 workload implementations** (18 framework benches + 15 one-shot memory binaries).
Sizeable — which is why the work is phased.

## Presentation / consumption

Local, **CLI-first**. The **folded-stacks intermediate is the hub** and feeds every consumer.

**Built (local):**
- **Text top-N summary** — the runner prints self/cumulative hot functions to stdout on every run.
  Works in any terminal or CI log, zero deps. The baseline every run emits.
- **`flamelens`** — interactive terminal **TUI flamegraph** over the folded stacks. The headless /
  server path; browser-free; works for every language.
- **inferno SVG** — still produced per workload/language as the portable, self-contained artifact
  (embedded click-to-zoom + Ctrl-F search); open in a browser when one is available. No gallery
  index or hosting scaffolding around it.

Text top-N, flamelens, and inferno SVG are **uniform across all six languages** (all fed by the
folded-stacks hub). The interactive **deep-dive viewer is per-language** — same capture, native tool:

- **Go / C++ / Rust:** `pprof -http` — interactive web UI (flamegraph / callgraph / source). Run on
  the server, port-forward.
- **Python:** `pyinstrument`'s own interactive HTML report (CPU) and `memray` (interactive HTML
  flamegraph + CLI `memray tree`/`summary`/`table`).
- **Java:** async-profiler's converter (`tools.profiler:jfr-converter`, consumed hermetically from
  Maven Central) → self-contained interactive HTML flamegraph (and collapsed output into the hub);
  JDK Mission Control for rich desktop JFR analysis; `jfr print` for a CLI text dump.

**Documented, not shipped (mirrors coverage's TeamCity sink):**
- **TeamCity self-hosted agent** — the natural home for the privileged, non-hermetic `perf`/`dtrace`
  path: a self-hosted / homelab agent can grant `perf` capabilities and gives the stable hardware
  shared CI runners can't. SVGs as an artifact / report tab, and benchmark timings pushed as
  `buildStatisticValue` for native trend charts. The README documents the setup; no `.teamcity`
  sample ships. Maps cleanly onto the dual-capture split — in-process runs anywhere, the perf
  sampler wants a self-hosted agent.

**Deferred (considered, not selected):**
- A local SVG gallery index, and a **GH Pages** `/profiling/` gallery reusing coverage's
  `deploy-pages` machinery (on-demand `workflow_dispatch`, not gating). Easy to add later — the
  plumbing already exists for coverage.

## Runner principle — profile runs are not measurement runs (→ README)

Profiling distorts timing — tracing profilers especially, but sampling too. The runner keeps
**measure** and **profile** as distinct modes: benchmark numbers are only ever quoted from
unprofiled runs. The CPU frameworks support the split natively (criterion `--profile-time`,
JMH `-prof`, `go test -cpuprofile`); the runner UX must preserve it, and the final README must
state it so consumers never quote timings from a profiled run.

## Open de-risking items

1. **Python folded adapters** — the residue of what was "per-language conversion is fiddly"
   after the pprof interchange model consolidated everything else. Two small in-repo pieces:
   pyinstrument → folded (~20-line renderer on its Session/Frame API) and memray → folded
   (~30-line adapter on its documented reader API). Closure: write both against a toy capture.
2. **gperftools Bazel packaging** — not cleanly in BCR (`com_google_tcmalloc` is a different thing).
   The C++ in-process CPU/heap profiler needs an `http_archive` / custom build. Named fallback if
   packaging fails: C/C++ in-process CPU documents the `perf` sampler as its only CPU path, and
   heap falls back to jemalloc's profiler (same pprof-readable output as the Rust path).
3. **`valgrind massif`** (C/C++ heap-over-time) is a non-flamegraph outlier — **deferred**;
   gperftools heap flamegraph (allocation sites) likely suffices for v1.
4. **JMH under Bazel** — JMH needs annotation-processor codegen and there is no maintained rules
   set (`buchgr/rules_jmh` is stale). Path forward for the implementing agent: add
   `org.openjdk.jmh:jmh-core` + `jmh-generator-annprocess` to `maven.install`, wire the processor
   as a `java_plugin` on the bench `java_library`, and run via a thin `java_binary` around
   `org.openjdk.jmh.Main` — replicate the ~30-line pattern in-repo rather than depend on the stale
   rules.
5. **Rust bin-crates + build scripts through crate_universe** — three assumptions to prove with
   one small trial (natural home: the Go pilot, which needs inferno anyway):
   inferno's binaries (`inferno-flamegraph`, `inferno-collapse-perf`, `inferno-collapse-dtrace`)
   and flamelens are *bin* crates — crate_universe builds libraries by default, so they need
   `gen_binaries` annotations and a proven `bazel run`; and `tikv-jemalloc-sys` builds jemalloc
   via its build script (autotools) — verify it builds in the sandbox. If flamelens won't build,
   it degrades to a documented host-installed tool; the other two have no fallback and must work.

## Phasing

Prove **one language end-to-end first** — bench → capture → folded → inferno SVG → the
`//tools/profile` runner — then replicate across the other five.

1. **Go pilot** — `runtime/pprof` is fully in-process and canonical, the cleanest path to a
   flamegraph. Validates the spine, the pprof2folded converter, the runner UX, and the
   crate_universe binaries trial (open item 5).
2. Add the **`perf` sampler path** to the same runner.
3. Replicate: **Rust** (pprof-rs → pprof → shared converter; heap via `jemalloc_pprof`) → **C++**
   (resolve the gperftools packaging probe) → **Python** (folded adapters, open item 1) →
   **Java** (JMH wiring, open item 4; `jfr-converter` from Maven Central).

Bench and memory-workload targets will live on the `_lib` modules (they hold the real logic worth
profiling). Runner UX TBD, e.g. `bazel run //tools/profile -- <target> --cpu|--mem
[--sampler=perf]` — with measure and profile as distinct modes (see runner principle).

## Carry into the final README

- **Profile runs are not measurement runs** — never quote timings from a run captured under a
  profiler (see runner principle).
- **The fragmentation workload is allocator-sensitive** — state per language which allocator's
  story it tells (Rust links jemalloc for profiling; C/C++ links tcmalloc when gperftools' heap
  profiler is active, glibc malloc otherwise).
