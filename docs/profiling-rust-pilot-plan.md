# feature:profiling — Phase 1: Rust pilot — implementation plan

> Status: **approved, execution in progress.** Companion to
> [profiling-feature-design.md](profiling-feature-design.md); execution tracked
> in the PR breakdown checkboxes below. Local planning notes — not user-facing
> product docs.

## Context

Implements Phase 1 of `docs/profiling-feature-design.md` (review complete): cross-language CPU+memory profiling driven by benchmark targets and rendered to flamegraphs, as the second composable `feature:` after coverage. The pilot proves the shared spine — capture → pprof → folded stacks → inferno SVG / flamelens TUI / text top-N — end-to-end for **one language, then replicates**. Pilot language changed from Go (doc) to **Rust** (user decision): pprof-rs has a native criterion integration, and the mandatory crate_universe bin-crates + jemalloc sandbox-build de-risking is Rust-side anyway.

## Decisions locked in discussion

- **Naming stem**: feature key/markers `feature:profiling`; runner `tools/profile` (`bazel run //tools/profile -- …`); output `/profile-out/`; config `build:profile`.
- **Workloads live in a NEW module `modules/rust_workloads`** (pattern: `<lang>_workloads` later) — hello-world `rust_lib` untouched.
- **Target names (uniform across all future languages)**: `bench_matmul`, `bench_quicksort`, `bench_pointer_chase` (criterion) + `mem_retained_growth`, `mem_string_churn`, `mem_fragmentation` (one-shot binaries; Rust is in the fragmentation set).
- **Tag-based discovery**: `tags = ["profiling-cpu"]` / `["profiling-mem"]`; runner uses `bazel query 'attr(tags, …)'`. Mode inferred from tag; `--cpu/--mem` filter `--all`/`--list` and assert on explicit targets.
- **Gazelle autogeneration of workload targets: deferred to replication phase** (opt-in directive polarity, unlike lint). Pilot hand-writes the 6 targets as the reference output; conventions above are the deterministic mapping a future generator needs.
- Workflow: PR-by-PR; user reviews and drives git/gh; commit/PR text staged in `tmp/`.

## Verified repo facts the plan relies on

- Bootstrap **never ships `modules/`** (scaffolder creates an empty code dir) → `modules/rust_workloads` needs **no manifest entry**.
- `tools/rust/Cargo.toml`, `go.mod`, `tools/go/go_segment.MODULE.bazel` are already `[composite_language_files]` → new `feature:profiling` marker blocks in them filter correctly. `tools/rust/rust_segment.MODULE.bazel` is NOT yet listed → must be added.
- Publish gazelle only emits for the rule named after the package basename; `# gazelle:publish_ignore` in the new BUILD closes the door.
- `[features.X].requires` auto-promotes languages. Profiling needs `requires = ["rust", "go", "python"]` (inferno/flamelens crates; pprofutils converter; py_binary runner — rules_python only ships with lang:python). Note: selecting profiling in bootstrap therefore pulls in three language toolchains.
- No `crate.annotation`/`gen_binaries` precedent exists — Spike A creates it.

## De-risking spikes (first, in order; artifacts feed the PRs)

**A — crate_universe `gen_binaries` for inferno + flamelens** (gates PR 2).
Cargo.toml: `inferno` (0.12), `flamelens` (0.3). rust_segment: `crate.annotation(crate = "inferno", gen_binaries = ["inferno-flamegraph"], repositories = ["crates"])` + same for flamelens. Verify: `CARGO_BAZEL_REPIN=1 bazel fetch @crates//...`; `bazel query '@crates//:all' | grep -i -e inferno -e flamelens` to discover exact generated-binary label names; `bazel run <label> -- --help`.
Fallbacks: inferno must work (it's the renderer — no fallback). flamelens is bin-only; if cargo/crate_universe refuses it, drop to `shutil.which("flamelens")` + documented `cargo install flamelens`.

**B — tikv-jemalloc-sys (autotools build script) + jemalloc_pprof in sandbox** (gates mem mode in PR 1).
Cargo.toml: `tikv-jemallocator` (0.6, `profiling` feature), `jemalloc_pprof` (0.8, `symbolize` feature). Trial binary: `#[global_allocator]` jemalloc + exported `_rjem_malloc_conf` static (`b"prof:true,prof_active:true,lg_prof_sample:19\0"`) + `PROF_CTL…dump_pprof()` → `$MEMPROF_OUT`.
Verify: sandboxed build succeeds; dumped pprof has symbolized frames (names, not hex); `_RJEM_MALLOC_CONF` env override works. Exact jemalloc_pprof API/version: verify during spike.
Fallbacks: `crate.annotation(build_script_env = …)` for build fixes; `pprof -proto -symbolize=force` pre-step if unsymbolized; worst case PR 1 ships CPU-only with the blocker documented.

**C — pprof-rs criterion integration under `bazel run`** (gates PR 1).
Cargo.toml: `criterion` + `pprof` (`criterion`, `protobuf-codec` features) — **verify version pairing** (pprof's criterion feature compiles against a specific criterion major). Minimal bench with `Criterion::default().with_profiler(PProfProfiler::new(100, Output::Protobuf))`.
Verify: `CRITERION_HOME=$PWD/profile-out/spike bazel run --config=profile //modules/rust_workloads:bench_matmul -- --bench --profile-time 5` produces `**/profile/profile.pb`; `-Cdebuginfo=2` via `--@rules_rust//rust/settings:extra_rustc_flags` survives `-c opt` and frames symbolize.
Fallbacks: explicit `ProfilerGuardBuilder` in bench main behind an env flag; comma-joined single `extra_rustc_flags` line if last-wins.

**D — pprofutils via go.mod** (gates PR 2).
`bazel run @rules_go//go -- get github.com/felixge/pprofutils/v2@latest` + `mod tidy` + `bazel mod tidy`. Verify the exact pprof→folded subcommand and the `go_binary` target path under `@com_github_felixge_pprofutils_v2//cmd/...`.
Fallback: ~40-line in-repo `tools/profile/pprof2folded/main.go` on `github.com/google/pprof/profile` (spine-compatible for all later languages).

## New module `modules/rust_workloads`

```
src/rust_workloads.rs   crate root; pub mods below
src/matmul.rs           multiply_ijk / multiply_ikj
src/quicksort.rs        in-place quicksort + seeded input gen
src/pointer_chase.rs    sattolo-cycle chase vs contiguous array sum
src/retained_growth.rs  reachable-but-unused growth
src/string_churn.rs     O(n²) concat churn
src/fragmentation.rs    alloc varied blocks, free every other, regrow
benches/bench_{matmul,quicksort,pointer_chase}.rs   criterion + PProfProfiler(Output::Protobuf)
mem/prof_dump.rs        shared shim: global_allocator + malloc_conf + dump (lives in bin crates, never the lib)
mem/mem_{retained_growth,string_churn,fragmentation}.rs   thin mains
tests/test_workloads.rs correctness (ijk==ikj, sorted output, chase sum == array sum, stats)
```

Quality bar: workload logic is idiomatic **library code** (capture shims only in `benches/`+`mem/`); randomness via the `rand` crate with `StdRng::seed_from_u64` (user-approved relaxation of the doc's stdlib-only bar — Rust's stdlib has no PRNG; input generation is setup code, so rand stays out of the measured profile); `N` read at runtime from `WORKLOAD_N` env (criterion owns argv; runner `--size` sets it); results through `black_box`.

BUILD: `# gazelle:publish_ignore`; `rust_library(rust_workloads, deps=["@crates//:rand"])`; `rust_test(rust_workloads_test)`; 3× `rust_binary(bench_*, deps=[lib, @crates//:criterion, @crates//:pprof], tags=["profiling-cpu"])`; 3× `rust_binary(mem_*, srcs=[main, "mem/prof_dump.rs"], deps=[lib, @crates//:tikv-jemallocator, @crates//:jemalloc_pprof], tags=["profiling-mem"])`; committed `.lint` siblings via `bazel run //:lint_gen`.

## `//tools/profile` runner (py_binary, stdlib-only, modeled on mint)

```
tools/profile/BUILD                    py_binary + py_library; data/env rlocationpaths for the
                                       inferno / flamelens / pprofutils binaries;
                                       deps @rules_python//python/runfiles; lint rules in
                                       feature:lint markers (mirror tools/publish/BUILD)
tools/profile/src/profile/__main__.py  entry point
tools/profile/src/profile/cli.py       argparse + BUILD_WORKSPACE_DIRECTORY (mirror mint/cli.py)
tools/profile/src/profile/engine.py    query discovery, bazel run subprocesses, mode inference (mirror mint/engine.py)
tools/profile/src/profile/spine.py     pb→folded (pprofutils), folded→SVG (inferno),
                                       folded→top-N text (stdlib parse), runfiles/which resolution
```

CLI: `bazel run //tools/profile -- [TARGET] [--all] [--list] [--cpu|--mem] [--measure] [--view] [--scope PATTERN] [--size N] [--profile-seconds S] [--out DIR]`. `--sampler=perf` parsed but rejected ("not yet implemented") to keep the flag surface stable for the follow-up phase.

Artifacts: `profile-out/<pkg_underscored>/<target>/{cpu|mem}/{profile.pb,profile.folded,flame.svg,top.txt}` — latest wins, no timestamps in v1.

- **CPU**: validate/infer via query → `bazel run --config=profile <label> -- --bench --profile-time S` with `CRITERION_HOME`, `WORKLOAD_N` → glob `**/profile/profile.pb` (per bench fn) → spine → top-N to stdout + `top.txt`.
- **Mem**: `bazel run --config=profile <label>` with `_RJEM_MALLOC_CONF`, `MEMPROF_OUT`, `WORKLOAD_N` → binary dumps pprof at exit → same spine.
- **Measure** (CPU only; refused for mem targets): `bazel run -c opt <label> -- --bench`, no profiler, criterion timings to terminal; print "timings only from measure runs".
- **View**: flamelens on a `.folded` (runfiles binary → `shutil.which` → actionable error).
- **--all/--list**: both tag queries under `--scope` (default `//...`), continue past failures, summarize.

## Cross-cutting file changes

| File | Change |
|---|---|
| `tools/rust/Cargo.toml` | `feature:profiling` marker block in `[dependencies]`: rand, criterion, pprof, inferno, flamelens, tikv-jemallocator, jemalloc_pprof (versions per spikes) |
| `tools/rust/Cargo.lock` | repin (`CARGO_BAZEL_REPIN=1 bazel fetch @crates//...`) |
| `tools/rust/rust_segment.MODULE.bazel` | `feature:profiling` block with the two `crate.annotation` calls |
| `go.mod` / `go.sum` | pprofutils require in `// --- BEGIN feature:profiling ---` markers / refreshed |
| `tools/go/go_segment.MODULE.bazel` | `feature:profiling` block: `use_repo(go_deps, "com_github_felixge_pprofutils_v2")` |
| `.bazelrc` | `feature:profiling` block: `build:profile --compilation_mode=opt`; nested `feature:profiling lang:rust` block: `build:profile --@rules_rust//rust/settings:extra_rustc_flags=-Cdebuginfo=2,-Cforce-frame-pointers=yes` (exact flags per Spike C) |
| `.gitignore` | `feature:profiling` block: `/profile-out/` |
| `MODULE.bazel` | **no change** (no new bazel_dep; deps ride existing @crates hub and go_deps) |

## Bootstrap + docs (PR 3)

`tools/bootstrap/bootstrap_manifest.toml`:
```toml
[features.profiling]
label = "Profiling (CPU + memory benches -> flamegraphs)"
requires = ["rust", "go", "python"]
directories = ["tools/profile"]
composite_files = ["tools/profile/BUILD"]   # feature:lint markers inside
```
plus add `"tools/rust/rust_segment.MODULE.bazel"` to `[composite_language_files].rust`. Mirror tests in `tools/bootstrap/tests/test_manifest.py` (`test_profiling_feature` + rust composite assertion). Optional 1-line AGENTS.md feature-list update.

Docs (what/how only, no rationale) in root `README.md` "## Profiling", `CLAUDE.md` "## Profiling", `tools/bootstrap/templates/README.md` (marker-gated; allocator note nested `feature:profiling lang:rust`): commands, output location, how to tag your own workload targets, **"profile runs are not measurement runs"**, **allocator sensitivity** (Rust memory workloads link jemalloc; fragmentation story is jemalloc's).

## PR breakdown (each independently green; user drives git/gh)

- [ ] **PR 1 — workloads + capture deps** (absorbs Spikes B, C): `modules/rust_workloads/**`, Cargo.toml block (criterion/pprof/jemalloc crates) + repin, `.bazelrc` + `.gitignore` blocks. Demoable by hand (`bazel run --config=profile …:bench_matmul -- --bench --profile-time 5`; `mem_*` dump `.pb`). Markers referencing a not-yet-declared feature are harmless.
- [ ] **PR 2 — spine + runner** (absorbs Spikes A, D): inferno/flamelens entries + annotations + repin, pprofutils go dep, `tools/profile/**`, end-to-end demo.
- [ ] **PR 3 — bootstrap feature + docs**: manifest, mirror tests, three doc surfaces, scaffold smoke test.

## Verification

```bash
# hygiene
bazel run //:buildifier.check
bazel run //:lint_gen && git diff --exit-code
bazel test //...
bazel test --config=raw //modules/rust_workloads/... //tools/profile/...
(cd tools/bootstrap && for t in tests/*.py; do PYTHONPATH=src python3 "$t"; done)

# CPU end-to-end (each bench; eyeball flame.svg: ijk vs ikj frames distinct, quicksort tower, symbols not hex)
bazel run //tools/profile -- --list
bazel run //tools/profile -- //modules/rust_workloads:bench_matmul

# memory end-to-end (each mem_*; eyeball allocation-site frames)
bazel run //tools/profile -- //modules/rust_workloads:mem_retained_growth

# measure/profile split (timings print, ikj < ijk, no profile.pb produced)
bazel run //tools/profile -- //modules/rust_workloads:bench_matmul --measure

# TUI + batch
bazel run //tools/profile -- --view profile-out/modules_rust_workloads/bench_matmul/cpu/profile.folded
bazel run //tools/profile -- --all

# bootstrap: scaffold with rust+profiling → go+python auto-promoted, tools/profile ships,
# marker blocks present, scaffolded repo builds, runner --list returns empty cleanly
bazel run //tools/bootstrap
```
