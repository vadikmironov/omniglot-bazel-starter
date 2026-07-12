package profiling_gazelle

// --- BEGIN lang:rust ---
import (
	"path"
	"strings"

	"github.com/bazelbuild/bazel-gazelle/language"
	"github.com/bazelbuild/bazel-gazelle/rule"
)

// memShim is the shared capture shim compiled into every memory
// workload binary (global jemalloc allocator + pprof heap dump).
const memShim = "mem/prof_dump.rs"

// generateRustWorkloads maps the package's Rust workload sources to
// runner-discoverable targets:
//
//	benches/bench_<x>.rs -> rust_binary(bench_<x>)  criterion + pprof, tagged profiling-cpu
//	mem/mem_<x>.rs       -> rust_binary(mem_<x>)    jemalloc capture, tagged profiling-mem,
//	                                                Linux-only (jemalloc_pprof upstream limit)
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
		r.SetAttr("deps", []string{":" + lib, "@crates//:criterion", "@crates//:pprof"})
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
		r.SetAttr("target_compatible_with", []string{"@platforms//os:linux"})
		r.SetAttr("deps", []string{":" + lib, "@crates//:jemalloc_pprof", "@crates//:tikv-jemallocator"})
		out = append(out, r)
	}
	return out
}

// --- END lang:rust ---
