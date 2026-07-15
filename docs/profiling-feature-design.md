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

1. **Python folded adapters** — **RESOLVED (Python phase, 2026-07)**: both adapters shipped at
   roughly the predicted size — pyinstrument → folded walks `Session.root_frame()` weighting
   stacks by `total_self_time` (synthetic `[self]` frames folded into their parents), and
   memray → folded sums `get_leaked_allocation_records()` sizes per stack (live-at-exit =
   the retained heap). They live in the workload package as the shared `benches/conftest.py`
   and `mem/prof_dump.py` shims, not in the runner — capture stays workload-side, folded is
   the interchange. The real Python finding was elsewhere: deficiencies item 4.
2. **gperftools Bazel packaging** — **RESOLVED (C++ phase, 2026-07)**: gperftools landed in BCR
   (2.18.1) with upstream Bazel support exposing `//:cpu_profiler` and `//:tcmalloc`; both build
   under the hermetic LLVM toolchain. Two probe findings shaped the capture path: (a) the
   `CPUPROFILE` env activation resolves its output path twice and pid-suffixes the real file, so
   benches use explicit `ProfilerStart/Stop` in a shared `prof_main.cpp` driven by `CPUPROF_OUT`;
   (b) both profilers emit gperftools' legacy format with raw addresses — the runner symbolizes
   it via google/pprof (a go.mod `tool`, like pprofutils) with `PPROF_TOOLS` pointed at the
   toolchain's own `llvm-symbolizer`, keeping the pipeline hermetic.

   macOS-build addendum (2026-07-14, caught by CI on the PR): gperftools has platform-conditional
   dead code — `/proc`-parsing helpers (`readlink_strdup`, `CopyStringUntilChar`,
   `StringToIntegerUntilCharWithCheck`) that are live on Linux but unused on Darwin, so
   `-Wunused-function` fires only on macOS and the repo-wide `-Werror` makes it fatal (a Linux-only
   local build never sees it). Rather than chase a per-warning, per-OS suppression list for a
   vendored library we don't maintain, the `.bazelrc` scopes `-Wno-error` to `external/gperftools.*`
   — its own warnings become non-fatal while first-party `-Werror` is untouched.

   **FOLLOW-UP — report (a) upstream to gperftools**: the pid-suffixing looks like a bug, not a
   design choice. `GetUniquePathFromEnv` (src/base/sysinfo.cc) sets `CPUPROFILE_USE_PID=1` in its
   own environment so that *forked children* uniquify their profile names — but profiler.cc
   resolves the path through it twice in the same process (once in `CpuProfilerSwitch`, once in
   the `CpuProfiler` constructor), and the second call sees the flag it just set for children:
   the real profile lands at `$CPUPROFILE_<pid>` while an empty file is created at `$CPUPROFILE`.
   Reproduced with gperftools 2.18.1, single-process binary, no fork. Check the upstream issue
   tracker for an existing report before filing; our explicit-API capture path is unaffected
   either way.
3. **`valgrind massif`** (C/C++ heap-over-time) is a non-flamegraph outlier — **deferred**;
   gperftools heap flamegraph (allocation sites) likely suffices for v1.
4. **JMH under Bazel** — **RESOLVED (Java phase, 2026-07)**: even simpler than planned — a
   single `java_binary` with `plugins = ["//tools/profile:jmh_annprocess"]` (a `java_plugin`
   on `jmh-generator-annprocess`) and `main_class = "org.openjdk.jmh.Main"` compiles the
   generated harness and the `META-INF/BenchmarkList` resource into the deploy jar; no
   intermediate `java_library`, no rules set. CPU capture via JMH's built-in `-prof jfr`
   (per-benchmark recordings); memory via a `jdk.jfr.Recording` API shim
   (`mem/ProfDump.java`) recording weighted `jdk.ObjectAllocationSample` events, stopped
   before dumping so the dump's own allocations stay out of the profile.
5. **Rust bin-crates + build scripts through crate_universe** — three assumptions to prove with
   one small trial (natural home: the Go pilot, which needs inferno anyway):
   inferno's binaries (`inferno-flamegraph`, `inferno-collapse-perf`, `inferno-collapse-dtrace`)
   and flamelens are *bin* crates — crate_universe builds libraries by default, so they need
   `gen_binaries` annotations and a proven `bazel run`; and `tikv-jemalloc-sys` builds jemalloc
   via its build script (autotools) — verify it builds in the sandbox. If flamelens won't build,
   it degrades to a documented host-installed tool; the other two have no fallback and must work.

## Profiling-stack deficiencies & upstream follow-ups

Started as a Rust/Go deep review after the C++ `CPUPROFILE` find (open item 2), extended with
the Java/Python phase probes: every place the shipped implementations work around upstream
deficiencies, with upstream status.

**FOLLOW-UPS (actionable):**

1. **pprofutils `folded` uses `sample.Value[0]` with no selector — Go/C++ memory renders are
   mislabeled today.** Heap profiles differ per language: Rust emits a single `inuse_space/bytes`
   (label "bytes" correct); Go emits `[alloc_objects, alloc_space, inuse_objects, inuse_space]`
   so folded counts **alloc_objects**; C++ (pprof-converted tcmalloc dump) emits
   `[objects/count, space/bytes]` so folded counts **objects** (verified: retained_growth's
   top.txt says 65537 = 64Ki chunks + 1 vector buffer, not 67108864 bytes). Both render under
   `countname="bytes"`. Upstream request already open: **felixge/pprofutils#15** ("folded: add
   support for specifying sample index"; their #14 is likely the same root) — a small Go PR
   candidate. Once it lands, the runner selects the index per profile and labels honestly.
   Coupled fix: switching Go to `inuse_space` requires the Go shim to lower
   `runtime.MemProfileRate` — the default 512 KiB sampling hides string_churn's ~128 KB live
   string, the same trap Rust solved with `lg_prof_sample:15`.
2. **jemalloc_pprof leaves its own profiling machinery in stack tails**
   (`…;_rjem_je_prof_tctx_create;_rjem_je_prof_backtrace;prof_backtrace_impl` — verified still
   present in 0.9). Worked around by `_trim_jemalloc_frames` in `tools/profile/src/profiling/spine.py`.
   No upstream issue exists — report to polarsignals/rust-jemalloc-pprof (strip machinery frames
   from `dump_pprof`, or document them).
3. **jfrconv (`tools.profiler:jfr-converter` 4.0) `--cpu` silently emits nothing for JDK-JFR
   recordings** (Java phase probe, 2026-07-13). Root cause, from the 4.0 converter source:
   `JfrConverter.getThreadStates(cpu=true)` admits only samples whose thread state is
   `STATE_DEFAULT` — the state async-profiler's *own* engine writes. JDK Flight Recorder
   `jdk.ExecutionSample` events carry real states (`STATE_RUNNABLE`), so a JDK recording
   converts to zero stacks; the 3.0 converter had no such filter and converted the same file
   fine. Still present on master (which only adds a separate `--cpuTime` mode); no upstream
   issue found — report to async-profiler/async-profiler (suggested fix: treat
   `STATE_RUNNABLE` as cpu-eligible, or fall back when the recording has no async-profiler
   events). **Our resolution: stay on 4.0 and pass `--state runnable` instead of `--cpu`** —
   verified sample-for-sample equivalent to 3.0's output, and 4.0 additionally normalizes the
   JIT-tier frame suffixes (`_[i]`/`_[j]`) that 3.0 splits aggregation on. `--alloc --total`
   is unaffected. Re-checked on the 4.4 bump (2026-07-15): `--cpu` still yields zero stacks
   from a JDK-JFR recording, so `--state runnable` stays. 4.4 also renamed the jar entrypoint
   `Main` -> `one.convert.Main` (the `jfrconv` `main_class` in `tools/profile/BUILD`).
4. **pytest-benchmark blanks `sys` profile hooks around every timed section and crashes
   restoring pyinstrument's** (Python phase probe, 2026-07-13). `PauseInstrumentation` in
   `pytest_benchmark/fixture.py` wraps calibration, warmup, and the measurement rounds,
   calling `sys.setprofile(None)` on entry — so a hook-based sampler like pyinstrument is
   *structurally blind* to the benchmark loops. Worse, its `__exit__` restores via
   `sys.setprofile(sys.getprofile())`, which raises `TypeError` for pyinstrument: C-level
   profilers (set via `PyEval_SetProfile`) surface a non-callable state object from
   `getprofile()` that the public `setprofile()` rejects — the restore both errors the test
   and kills the profiler. Two upstream reports for pytest-benchmark: the crash (any C-level
   profiler active during a bench run breaks the session) and, softer, an option to skip the
   pausing. **Our resolution: in profile mode (CPUPROF_OUT set) the bench conftest
   monkeypatches `PauseInstrumentation` to a no-op** — profiled runs are never measurement
   runs, so sampling the real loops with distorted timings is exactly the trade we want;
   measure mode leaves pytest-benchmark untouched.

**Known upstream — track, don't file:**

- **pprof-rs pins criterion `^0.5`** while criterion is at 0.8.2 — the Cargo.toml
  "keep majors in sync" comment is load-bearing, and a Renovate criterion-major bump would break
  resolution. Upstream: tikv/pprof-rs#284 (criterion 0.8) open, with older #269/#271 (0.6) —
  nudge or review there.
- **jemalloc_pprof macOS unsupported** — upstream #36 (compounded by jemalloc's autotools build
  failing under the hermetic macOS toolchain); `mem_*` stays Linux-gated, the dtrace phase
  remains the designed macOS story.
- **jemalloc_pprof `PROF_CTL` is an async (tokio) mutex** — upstream #30; the one-shot shim
  calls `.blocking_lock()` and pulls tokio into every mem workload binary. Cosmetic dep bloat.
- **purego < 0.10.1 ICEs the Go 1.26 compiler** — pinned past it (rust-pilot doc); it arrived
  via pprofutils → dd-trace-go. A folded converter dragging the DataDog tracing tree into go.mod
  is itself a wart; no upstream issue about slimming it.

**Accommodations by design (documented so nobody "simplifies" them away):**

- criterion activates profilers only under `--profile-time` — the runner always passes it; slow
  benches carry `sample_size(10)` to fit criterion's measurement window.
- pprof-rs's default unwinder wants frame pointers — the `.bazelrc`
  `-Cforce-frame-pointers=yes,-Cdebuginfo=2` line exists for it (pprof-rs DWARF support is weak:
  their #152 "Make DWARF great again"); exactly parallel to the C++
  `-g -fno-omit-frame-pointer` line.
- Go's `runtime.GC()` before the heap dump is canonical live-set practice; Go CPU capture
  (`-test.cpuprofile`) needed no workaround at all — the cleanest of the three.
- CPU-side folded counts are correct everywhere (CPU profiles lead with `samples/count`,
  matching `countname="samples"`) — the sample-index issue is memory-only.

## Phasing

Prove **one language end-to-end first** — bench → capture → folded → inferno SVG → the
`//tools/profile` runner — then replicate across the other five.

1. **Go pilot** — `runtime/pprof` is fully in-process and canonical, the cleanest path to a
   flamegraph. Validates the spine, the pprof2folded converter, the runner UX, and the
   crate_universe binaries trial (open item 5).
2. Add the **`perf` sampler path** to the same runner.
3. Replicate: **Rust** (pprof-rs → pprof → shared converter; heap via `jemalloc_pprof`) ✓ →
   **C++** (gperftools packaging probe resolved — see open item 2) ✓ → **Python** (folded
   adapters — shipped as the bench conftest and memray shim; see deficiencies item 4 for the
   pytest-benchmark interplay) ✓ → **Java** (JMH via a `java_plugin` annotation processor on
   plain `java_binary` targets — no rules needed; jfrconv from Maven Central, deficiencies
   item 3) ✓. **All five languages replicated 2026-07-13.**

Bench and memory-workload targets will live on the `_lib` modules (they hold the real logic worth
profiling). Runner UX TBD, e.g. `bazel run //tools/profile -- <target> --cpu|--mem
[--sampler=perf]` — with measure and profile as distinct modes (see runner principle).

## Carry into the final README

- **Profile runs are not measurement runs** — never quote timings from a run captured under a
  profiler (see runner principle).
- **The fragmentation workload is allocator-sensitive** — state per language which allocator's
  story it tells (Rust links jemalloc for profiling; C/C++ links tcmalloc when gperftools' heap
  profiler is active, glibc malloc otherwise).
