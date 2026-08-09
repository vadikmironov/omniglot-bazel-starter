package profiling_gazelle

// --- BEGIN lang:rust ---
import (
	"path"
	"strings"

	"github.com/bazelbuild/bazel-gazelle/language"
	"github.com/bazelbuild/bazel-gazelle/rule"
)

// criterionPprofDep supplies CPU capture to every criterion bench: a criterion
// Profiler backed by pprof-rs, which a bench installs with
// `Criterion::default().with_profiler(PProfProfiler::new(100))`. pprof-rs ships
// an equivalent behind its own `criterion` feature, but that feature depends on
// criterion 0.5 and would pin every bench to it.
const criterionPprofDep = "//tools/profile/criterion_pprof"

// memShim is the shared capture shim compiled into every memory
// workload binary (tcmalloc heap profiler, driven over FFI).
const memShim = "mem/prof_dump.rs"

// tcmalloc supplies the heap profiler for Rust memory workloads, exactly as it
// does for C++. Linking it is enough — it interposes malloc/free, so Rust's
// allocations are captured without a #[global_allocator] — and it reports live
// *and* cumulative bytes *and* object counts, which jemalloc cannot: jemalloc
// removed opt.prof_accum in 5.0.0 because cumulative counts oblige it to retain
// every unique backtrace for the life of the process.
//
// It goes in link_deps, not deps: rules_rust deprecates C++ libraries in deps
// and directs manual FFI linkage here.
const tcmallocDep = "@gperftools//:tcmalloc"

// generateRustWorkloads maps the package's Rust workload sources to
// runner-discoverable targets:
//
//	benches/bench_<x>.rs -> rust_binary(bench_<x>)  criterion + the shared
//	                                                pprof profiler, tagged profiling-cpu
//	mem/mem_<x>.rs       -> rust_binary(mem_<x>)    tcmalloc capture, tagged profiling-mem
//
// Each target depends on the package's canonical library (the rule
// named after the package basename), which holds the workload logic;
// if that rule is absent nothing is generated.
func generateRustWorkloads(args language.GenerateArgs) []*rule.Rule {
	lib := path.Base(args.Rel)
	if args.Rel == "" || !hasRule(args, lib) {
		return nil
	}

	var out []*rule.Rule
	for _, src := range globWorkloads(args.Dir, "benches", "bench_", ".rs") {
		name := strings.TrimSuffix(path.Base(src), ".rs")
		r := rule.NewRule(kindRustBinary, name)
		r.SetAttr("srcs", []string{src})
		r.SetAttr("tags", []string{tagCPU})
		r.SetAttr("deps", []string{":" + lib, "@crates//:criterion", criterionPprofDep})
		out = append(out, r)
	}

	hasShim := len(globWorkloads(args.Dir, "mem", "prof_dump", ".rs")) > 0
	for _, src := range globWorkloads(args.Dir, "mem", "mem_", ".rs") {
		name := strings.TrimSuffix(path.Base(src), ".rs")
		srcs := []string{src}
		if hasShim {
			srcs = append(srcs, memShim)
		}
		r := rule.NewRule(kindRustBinary, name)
		r.SetAttr("srcs", srcs)
		r.SetAttr("crate_root", src)
		r.SetAttr("tags", []string{tagMem})
		r.SetAttr("deps", []string{":" + lib})
		r.SetAttr("link_deps", []string{tcmallocDep})
		out = append(out, r)
	}
	return out
}

// --- END lang:rust ---
