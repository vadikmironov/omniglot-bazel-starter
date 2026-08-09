# `feature:profiling` — design

> **Status: shipped** for Rust, Go, C++, Python and Java. Second composable feature after
> `feature:coverage`, same `feature:` bootstrap-segment model. Local design notes — the
> user-facing docs are README "## Profiling", `CLAUDE.md`, and the marker-gated scaffold
> template. What landed when is at the end, in [Changelog](#changelog).

## Goal

Cross-language **CPU and memory profiling** driven by dedicated benchmark targets, rendered to
flamegraphs. The same composable-segment approach as coverage: per-language capture feeds one
shared renderer.

Designed for C, C++, Go, Java, Python, Rust; shipped for five — C has no workloads of its own,
since the design always hosted C benches in the C++ harness (google/benchmark), and
`modules/c_library` is not profiled today.

## Locked decisions

| Decision | Choice |
|---|---|
| Scope | **Both CPU and memory** profiling |
| Workload | **Dedicated benchmark targets** (profiling has no free spine like coverage's test suite — it needs something running to measure) |
| Workload hosting | **Split by kind.** CPU benches live in the idiomatic bench frameworks. **Memory workloads are plain one-shot binaries** the runner executes once under the profiler — bench frameworks calibrate and re-run the body N times, which contaminates leak / heap-over-time workloads (growth scales with iteration count). Bonus: shrinks the JMH / pytest-benchmark integration surface to CPU only |
| Bench frameworks (CPU) | **Idiomatic per language**: Go `testing.B`, Rust criterion, C++ google/benchmark (also hosts the C benches — the harness is C++, the workload code stays C), Java JMH, Python pytest-benchmark |
| Posture | **Local / on-demand only** — no CI job, no gating (perf numbers are too noisy on CI runners). The one profiling-related CI check captures nothing: `profile_gen` convergence, beside `lint_gen` / `publish_gen` |
| Capture | **Dual** — in-process/hermetic default + non-hermetic system-sampling opt-in |
| Renderer | **inferno** (`rules_rust`) — the Rust rewrite of `flamegraph.pl`; builds hermetically through the existing Rust toolchain |

## Architecture

**Spine** (mirrors coverage's LCOV → genhtml): per-language capture → **collapsed / folded stacks**
→ `inferno-flamegraph` → SVG. `pprof` stays a richer *secondary* view (interactive callgraph / web
UI) for the languages that speak it natively.

**Interchange — pprof protobuf is the inner lingua franca.** Every capture tool that can emit pprof
does: Go CPU/heap, pprof-rs (Rust CPU), and gperftools CPU/heap — which covers C/C++ *and* Rust
heap, since Rust's memory capture links the same tcmalloc profiler. One hermetic converter,
`//tools/profile/pb2folded` (~240 lines of first-party Go over `github.com/google/pprof/profile`),
turns all of them into folded stacks, and additionally emits every sample type at once as TSV for
the four-bucket memory report. Its conversion contract lives in the code.

Bespoke conversion remains for exactly two languages:

- **Java:** JFR → collapsed via async-profiler's converter, a **pure-Java jar on Maven Central**
  (`tools.profiler:jfr-converter`). Slots straight into the existing `maven.install`; fully
  hermetic, no binary downloads.
- **Python:** two small in-repo adapters that skip pprof entirely — pyinstrument → folded (walks
  `Session.root_frame()`, weighting stacks by `total_self_time`, synthetic `[self]` frames folded
  into their parents) and memray → folded (sums `get_leaked_allocation_records()` sizes per stack).
  Both live workload-side, in `benches/conftest.py` and `mem/prof_dump.py`, not in the runner:
  capture stays per-language, folded is the interchange.

C++ and Rust need one extra hop: gperftools writes its legacy format with raw addresses, so the
runner symbolizes with google/pprof (a `go.mod` `tool` directive) and `PPROF_TOOLS` pointed at the
toolchain's own `llvm-symbolizer` — hermetic, and it demangles Rust's v0 symbols too.

### Capture is dual

- **Default — in-process / hermetic.** Privilege-free, no `perf`/root/`ptrace`, cross-platform,
  matches the hermetic-toolchain ethos. Requires instrumenting each bench binary.
- **Opt-in — non-hermetic system sampling.** Uses host tools (not Bazel-provided), needs privileges
  (`perf_event_paranoid` / `ptrace`), platform-specific. No code instrumentation; sees kernel /
  syscall / off-CPU frames the in-process path cannot. `perf` on Linux is shipped as
  `--sampler=perf`; `dtrace` on macOS is designed but not built, so macOS has no system-sampler
  path today.

  Synergy with the renderer: inferno ships `inferno-collapse-perf` and `inferno-collapse-dtrace`,
  so both external samplers feed the same renderer with **zero extra converters**.
  (`perf` = Linux, `dtrace` = macOS/BSD; the Linux dtrace port is fringe and out of scope.)

### Per-language capture matrix

All privilege-free, everything reaches pprof or collapsed stacks → inferno. "Memory buckets" is how
much of alloc/inuse × objects/bytes each capture can actually fill.

| Lang | Bench framework (CPU) | CPU | Memory | Memory buckets | interchange |
|---|---|---|---|---|---|
| Go | `testing.B` | `runtime/pprof` | heap pprof | all four, sampled every 32 KiB (`MemProfileRate`) | pprof |
| Rust | criterion | `pprof-rs` | gperftools `tcmalloc` heap profiler over FFI | all four, exact | pprof |
| C++ / C | google/benchmark | gperftools | gperftools heap (`tcmalloc`) | all four, exact | pprof |
| Python | pytest-benchmark | `pyinstrument` | `memray` | all four, exact (bytes include CPython object overhead) | folded via in-repo adapters |
| Java | JMH | JFR | JFR alloc (`jdk.ObjectAllocationSample`) | `alloc_space` only — throttled samples carry no object count, and `jdk.OldObjectSample` (live) carries no size | JFR → collapsed via jfr-converter |

Java is the one asymmetry: the derived ratios that need the other three buckets report as
unavailable rather than guessing, and enabling `jdk.OldObjectSample` (`jfrconv --live`) would add a
leak-sampler view, not byte-accurate live-heap accounting. Per-language rationale lives beside the
shims in `modules/<lang>_workloads/mem/README.md`.

Two capture choices were made against the obvious defaults, both for hub convergence with
maintained tools: **Python CPU is pyinstrument, not cProfile** (cProfile records caller→callee
edges, not full stacks, so folded output from it is a reconstruction, and the known converter
`flameprof` is unmaintained), and **Rust heap is tcmalloc, not jemalloc or dhat** (dhat's JSON is a
format island; jemalloc can only ever report live bytes — see Changelog, 2026-07-26).

## Benchmark workloads

Chosen via a weighted scored comparison. The headline criterion is **profiler↔in-process contrast**
(weighted ×2) — does the workload reveal something the *system* profiler (`perf` / `dtrace` /
`massif`) shows that an in-process profiler cannot? — because that contrast is the whole reason the
non-hermetic path exists.

**Key finding:** no single workload maximizes every aspect. For CPU, flamegraph legibility and
hardware-counter contrast pull in *opposite* directions (cache/branch workloads have flat
flamegraphs; recursive workloads have rich flamegraphs but dull counters). So a **covering set**
beats any single workload.

### CPU set — every language

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
| **Unbounded retained growth (logical leak)** | all | The live-heap teacher: massif's heap-over-time curve vs in-process *where-allocated* attribution. Portable — a "reachable-but-unused" leak works in GC languages too. |
| **String-concat O(n²) churn** | all | Allocation-*rate* / transient churn that in-process alloc profilers reveal but RSS/peak snapshots miss — the mirror image of the leak. |
| **Fragmentation** (free every other, realloc larger) | C / C++ / Rust | RSS stays high while live bytes drop — the external↔in-process poster child. Reproduces only on manual allocators; GC languages compact/manage the heap. |

*Rejected as everywhere-workloads:* word-count / tree-build / batch-pipeline (portable but low
external contrast). Word-count is the fallback if a fully-portable third is ever wanted.

**Allocator sensitivity (→ README):** the fragmentation story depends on which allocator the binary
links. C/C++ **and Rust** link tcmalloc when gperftools' heap profiler is active (the profiler
lives in tcmalloc) and their default allocator otherwise — so all three fragmentation workloads
tell tcmalloc's story and their numbers are directly comparable. Each language's README entry
states whose allocator story it tells.

### Quality bar

Every implementation must be: identical & idiomatic across languages, **stdlib-only** (no library
that would dominate the profile), deterministic (seeded, no I/O), tunable by a size `N`, and
resistant to being optimized away (read `N` at runtime, pass results through the bench framework's
`black_box`). `N` arrives as `WORKLOAD_N` (the runner's `--size`), since criterion and JMH own
argv. One relaxation: Rust uses the `rand` crate for seeded input generation
(`StdRng::seed_from_u64`) — the stdlib has no PRNG, and input generation is setup code outside the
measured region.

**As designed:** 3 CPU + 2 memory across 6 languages, + fragmentation on C/C++/Rust = 33
implementations. **As shipped:** 27 across five languages (15 framework benches + 12 one-shot
memory binaries) in `modules/{rust,go,cpp,python,java}_workloads`.

### How targets are declared

Discovery is by tag — `profiling-cpu` (framework benches) and `profiling-mem` (one-shot binaries) —
and the tagged targets are *generated*. A package opts in with `# gazelle:profiling`;
`bazel run //:profile_gen` maps `benches/` and `mem/` sources onto `bench_*` / `mem_*` targets
wired to the package's library, and reaps orphans. Ownership is name-prefix + tag, so hand-written
tagged targets survive untouched and packages without the directive are never modified — opt-in
polarity, unlike `lint_gen`.

## Presentation / consumption

Local, **CLI-first**. The **folded-stacks intermediate is the hub** and feeds every consumer.

**Built, and uniform across all five languages:**
- **Text summary** on every run — CPU prints self/cumulative hot functions; memory prints the
  four-bucket self-weight table and the derived ratios (`spine.bucket_report`). Works in any
  terminal or CI log, zero deps.
- **`flamelens`** — interactive terminal TUI flamegraph over the folded stacks. The headless /
  server path; browser-free.
- **inferno SVG** — the portable, self-contained artifact (embedded click-to-zoom + Ctrl-F search);
  open in a browser when one is available. No gallery index or hosting scaffolding around it.

The interactive **deep-dive viewer is per-language** — same capture, native tool, none of them
wired into the runner: `pprof -http` for Go / C++ / Rust; pyinstrument's own HTML report and
memray's HTML flamegraph + `memray tree`/`summary`/`table` for Python; jfr-converter's HTML
flamegraph, JDK Mission Control and `jfr print` for Java.

## Runner principle — profile runs are not measurement runs

Profiling distorts timing — tracing profilers especially, but sampling too. The runner keeps
**measure** and **profile** as distinct modes: benchmark numbers are only ever quoted from
unprofiled runs. The CPU frameworks support the split natively (criterion `--profile-time`, JMH
`-prof`, `go test -cpuprofile`). Shipped as `--measure` (CPU targets only — it refuses memory
ones), and stated in README, `CLAUDE.md` and the scaffold template.

Full CLI: `bazel run //tools/profile -- [TARGET] [--all|--list] [--cpu|--mem] [--measure] [--view]
[--sampler=perf] [--scope P] [--size N] [--profile-seconds S] [--out DIR]`.

## Accommodations by design

Load-bearing quirks — documented so nobody "simplifies" them away:

- **criterion** activates profilers only under `--profile-time` — the runner always passes it; slow
  benches carry `sample_size(10)` to fit criterion's measurement window.
- **pprof-rs**'s default unwinder wants frame pointers — the `.bazelrc`
  `-Cforce-frame-pointers=yes,-Cdebuginfo=2` line exists for it (their DWARF support is weak:
  pprof-rs#152); exactly parallel to the C++ `-g -fno-omit-frame-pointer` line.
- **The criterion `Profiler` is implemented in-repo** (`//tools/profile/criterion_pprof`), and
  pprof-rs's own `criterion` feature stays off — that feature carries a criterion 0.5 dependency,
  and the Rust benches should be free to follow criterion's releases. Two trait methods over
  pprof's core API; the output contract is unchanged (`profile.pb` in criterion's per-benchmark
  directory). It lives in `tools/profile` rather than beside the workloads because it is a fixed
  adapter between two crates with no per-package variation — the same reasoning that puts
  `jmh_annprocess` and `jfrconv` there. Shims that must be *compiled into* the workload binary
  (C++'s `benches/prof_main.cpp`, Python's `benches/conftest.py`, the `mem/prof_dump.*` capture
  shims) stay per-package.
- **gperftools** capture uses explicit `ProfilerStart`/`ProfilerStop` in a shared `prof_main.cpp`
  driven by `CPUPROF_OUT`, never the `CPUPROFILE` env activation — that path pid-suffixes the real
  file (upstream bug, below).
- **`.bazelrc` scopes `-Wno-error` to `external/gperftools.*`** — gperftools' `/proc`-parsing
  helpers are dead code on Darwin, so `-Wunused-function` fires only on macOS and the repo-wide
  `-Werror` makes it fatal. First-party `-Werror` is untouched.
- **jfrconv gets `--state runnable`, not `--cpu`** — `--cpu` yields zero stacks from JDK-JFR
  recordings (upstream bug, below).
- **The Python bench conftest no-ops `PauseInstrumentation` in profile mode** — otherwise
  pytest-benchmark blanks the sampler around exactly the loops worth sampling (upstream bug, below).
- **Go dumps after `runtime.GC()`** (canonical live-set practice) at a 32 KiB `MemProfileRate`
  matching the other languages, and workloads must hold their result across the dump with
  `runtime.KeepAlive` or the dump's own GC collects it.
- **CPU-side folded counts are correct everywhere** (CPU profiles lead with `samples/count`) — the
  sample-type selection above matters only for memory.

## Still open

**Deferred, none blocked:**

- **`dtrace` / macOS sampler** — the designed macOS counterpart to `--sampler=perf`; inferno's
  `inferno-collapse-dtrace` means it needs no new converter.
- **`valgrind massif`** (C/C++ heap-over-time) — a non-flamegraph outlier. The gperftools heap
  flamegraph sufficed for v1, and the four-bucket report now gives turnover and live-vs-RSS numbers
  without an external tool.
- **SVG gallery index / GH Pages `/profiling/`** reusing coverage's `deploy-pages` machinery
  (on-demand `workflow_dispatch`, not gating). The plumbing already exists for coverage.
- **TeamCity self-hosted `perf` sink** — designed as documented-not-shipped (mirroring coverage's
  TeamCity sink): a self-hosted agent can grant `perf` capabilities and gives stable hardware, with
  SVGs as artifacts and timings pushed as `buildStatisticValue`. The README section was never
  written — its TeamCity block covers coverage only.
- **Java's live-heap bucket** — see the matrix note.
- **`modules/python_workloads/mem/README.md`** — the one language without a memory-shim README.

**Upstream reports to file:**

- **gperftools** — `CPUPROFILE` pid-suffixes the real profile. `GetUniquePathFromEnv`
  (`src/base/sysinfo.cc`) sets `CPUPROFILE_USE_PID=1` in its own environment so *forked children*
  uniquify their names, but `profiler.cc` resolves the path through it twice in the same process
  (`CpuProfilerSwitch`, then the `CpuProfiler` constructor) and the second call sees the flag it
  just set: the profile lands at `$CPUPROFILE_<pid>` and an empty file at `$CPUPROFILE`. Reproduced
  on 2.18.1, single-process, no fork. Check their tracker for an existing report first.
- **async-profiler** — jfrconv `--cpu` emits nothing for JDK-JFR recordings.
  `JfrConverter.getThreadStates(cpu=true)` admits only `STATE_DEFAULT`, the state async-profiler's
  own engine writes; JDK `jdk.ExecutionSample` events carry `STATE_RUNNABLE`, so a JDK recording
  converts to zero stacks. The 3.0 converter had no such filter. Still present on master (which
  only adds a separate `--cpuTime` mode). Suggested fix: treat `STATE_RUNNABLE` as cpu-eligible, or
  fall back when the recording has no async-profiler events.
- **pytest-benchmark ×2** — (a) the crash: `PauseInstrumentation.__exit__` restores via
  `sys.setprofile(sys.getprofile())`, which raises `TypeError` for any C-level profiler (set via
  `PyEval_SetProfile`), since `getprofile()` surfaces a non-callable state object the public
  `setprofile()` rejects — this both errors the test and kills the profiler. (b) softer: an option
  to skip the pausing at all, since it blanks `sys` hooks around calibration, warmup and every
  measurement round, leaving hook-based samplers structurally blind to the benchmark loops.

**Track, don't file:**

- **pprof-rs's `criterion` feature depends on criterion `^0.5`** while criterion is at 0.8.x.
  Upstream PRs offering the bump are open (tikv/pprof-rs#284 for 0.8, #269/#271 for 0.6) and the
  repository has been quiet since October 2025, so no fix is expected on a schedule. **Resolved
  locally** by implementing criterion's `Profiler` in `//tools/profile/criterion_pprof` and leaving
  the feature off, which unpinned criterion (see Changelog, 2026-08-09) — nothing left to track
  unless pprof-rs's core sampling API changes.
- **`go mod tidy` is broken repo-wide, and not by anything of ours.** From gazelle v0.52.0 the
  `github.com/bazelbuild/bazel-gazelle` packages became shims re-exporting
  `github.com/bazel-contrib/bazel-gazelle/v2/...`, but the published v2 module (v2.0.0-1, v2.0.0-2)
  ships only `cmd, flag, internal, label, merger, pathtools, rule, testtools` — the `config`,
  `resolve`, `language` and `repo` packages our gazelle extensions import do not exist there, and a
  `replace` cannot bridge it (the republished module's go.mod still declares the bazelbuild path).
  **Worked around** by holding go.mod at `bazel-gazelle v0.51.3` while MODULE.bazel keeps 0.52.2;
  Bazel is unaffected because `@gazelle//config` and friends declare the old importpath and build
  from gazelle's own sources. Cost: a `go_deps` version-skew DEBUG on re-evaluation. Realign once
  upstream publishes a complete v2.

## Changelog

**2026-08-09 — criterion 0.8; Rust CPU capture decoupled from pprof-rs's criterion feature.**
That feature depends on criterion 0.5, so every Rust bench was held there while criterion shipped
0.6, 0.7 and 0.8. criterion's `Profiler` trait is two methods and pprof-rs's sampling API is public,
so the integration now lives in `//tools/profile/criterion_pprof` — modelled on pprof-rs's own,
minus the `Output` enum, since the runner only ever consumed protobuf. Generated bench targets
depend on it (bootstrapped repos get it with the feature, as they do `jmh_annprocess`), `pprof`
keeps `protobuf-codec` alone, and criterion tracks its own releases from here. Two guards came with
it: a `rust_test` driving the trait directly and parsing the `profile.pb` it writes, and a bootstrap
regression test asserting every workspace label a gazelle generator emits resolves to a package the
manifest ships — the failure mode that a capture component beside the example workloads would have
had, since example modules never scaffold.

**2026-07-26 — memory correctness pass** (unplanned). `felixge/pprofutils` folded a hardcoded sample
index, so Go and C++ heap renders labelled object counts as bytes; its open fix request
(pprofutils#15) is unmerged, so it was replaced by first-party `//tools/profile/pb2folded` — which
also shed the `dd-trace-go` tree pprofutils dragged in (~30 indirect requires) and the purego pin
that tree required. Added the four-bucket report (alloc/inuse × objects/bytes) with derived
turnover, mean-size and live-over-RSS ratios. Rust heap capture moved from jemalloc to tcmalloc:
jemalloc removed `opt.prof_accum` in 5.0.0, putting cumulative counts permanently out of reach,
while tcmalloc gives Rust all four buckets exactly and byte-identical to C++ — at the cost of gating
Rust *memory* profiling on `lang:cpp`.

**2026-07-22 — jfr-converter 4.5** (Renovate batch). Workaround and entrypoint carried over
unchanged and Java CPU profiling stayed green; `--cpu` was not re-probed.

**2026-07-15 — jfr-converter 4.4.** `--cpu` still yields zero stacks from JDK-JFR recordings, so
`--state runnable` stays; 4.4 normalizes the JIT-tier frame suffixes (`_[i]`/`_[j]`) that 3.0 split
aggregation on, and renamed the jar entrypoint `Main` → `one.convert.Main`.

**2026-07-14 — gperftools on macOS** (caught by CI). Platform-conditional dead code
(`readlink_strdup`, `CopyStringUntilChar`, `StringToIntegerUntilCharWithCheck`) trips
`-Wunused-function` only on Darwin, fatal under the repo-wide `-Werror`. Fixed by scoping
`-Wno-error` to `external/gperftools.*` rather than chasing a per-warning, per-OS suppression list
for a library we don't maintain.

**2026-07-13 — replication complete; all five languages.** Opened by the **gazelle workload
generator** (`# gazelle:profiling` + `//:profile_gen`, `-profiling_remove` teardown wired into
bootstrap, CI convergence check) with `modules/rust_workloads` converted to generated form
attribute-for-attribute, and **Go** (`testing.B` + `-test.cpuprofile`; `runtime/pprof` heap dumps,
cross-platform). Then **C++**: gperftools had landed in BCR (2.18.1) with upstream Bazel support
exposing `//:cpu_profiler` and `//:tcmalloc`, both building under the hermetic LLVM toolchain — the
packaging probe the design flagged as the one real unknown. Then **Python**: both folded adapters
shipped at roughly the predicted size, and the real finding was pytest-benchmark's instrumentation
blanking. Then **Java**: simpler than planned — a single `java_binary` with `plugins =
["//tools/profile:jmh_annprocess"]` and `main_class = "org.openjdk.jmh.Main"` compiles the generated
harness and the `META-INF/BenchmarkList` resource into the deploy jar, no intermediate
`java_library` and no rules set; CPU via JMH's `-prof jfr`, memory via a `jdk.jfr.Recording` shim
recording weighted `jdk.ObjectAllocationSample` events, stopped before dumping so the dump's own
allocations stay out. The runner dispatches bench flavors by rule kind, and its docs were rewritten
language-independent around the shared contract.

**2026-07-12 — `perf` sampler** (PR #54). `--sampler=perf` on CPU benches with prereq checks (host
perf, `perf_event_paranoid` ≤ 2); perf wraps the built binary directly and
`perf script | inferno-collapse-perf` rejoins the shared spine, emitting `<target>-perf.*` beside
the in-process per-function artifacts.

**2026-07-11 — pilot, spine and runner** (PR #52). The design named Go as the pilot; it shipped as
**Rust**, because pprof-rs has a native criterion integration and the mandatory crate_universe
bin-crate trial was Rust-side anyway. That trial resolved the last dependency unknown: `gen_binaries`
annotations produce `@crates//:inferno__inferno-flamegraph` and `@crates//:flamelens__flamelens`,
both `bazel run`-able, so flamelens never needed its host-install fallback. Also settled here:
pprof 0.15 pairs with criterion 0.5 via `protobuf-codec` (prost needs a host protoc); the runner's
Python package is `profiling`, not `profile`, to avoid shadowing the stdlib module (hence
`tools/profile/src/profiling/`); and `--incompatible_default_to_explicit_init_py` went repo-wide
after the runner surfaced rules_python's implicit-`__init__` deprecation. Memory capture was
jemalloc-based and Linux-only until the 2026-07-26 pass.
