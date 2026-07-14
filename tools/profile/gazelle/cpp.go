package profiling_gazelle

// --- BEGIN lang:cpp ---
import (
	"path"
	"strings"

	"github.com/bazelbuild/bazel-gazelle/language"
	"github.com/bazelbuild/bazel-gazelle/rule"
)

// cppBenchMain is the shared bench entrypoint compiled into every CPU
// bench binary (google/benchmark main wrapped in gperftools
// ProfilerStart/Stop). cppMemShim* form the shared capture shim for
// memory workload binaries (tcmalloc heap profiler dumped in
// gperftools' legacy format).
const (
	cppBenchMain  = "benches/prof_main.cpp"
	cppMemShimSrc = "mem/prof_dump.cpp"
	cppMemShimHdr = "mem/prof_dump.h"
)

// generateCppWorkloads maps the package's C++ workload sources to
// runner-discoverable targets:
//
//	benches/bench_<x>.cpp -> cc_binary(bench_<x>)  google/benchmark + gperftools
//	                                               CPU profiler, tagged profiling-cpu
//	mem/mem_<x>.cpp       -> cc_binary(mem_<x>)    tcmalloc heap capture, tagged profiling-mem
//
// Each target depends on the package's canonical library (the rule
// named after the package basename), which holds the workload logic;
// if that rule is absent nothing is generated.
func generateCppWorkloads(args language.GenerateArgs) []*rule.Rule {
	lib := path.Base(args.Rel)
	if args.Rel == "" || !hasRule(args, lib) {
		return nil
	}

	var out []*rule.Rule
	hasBenchMain := len(globWorkloads(args.Dir, "benches", "prof_main", ".cpp")) > 0
	for _, src := range globWorkloads(args.Dir, "benches", "bench_", ".cpp") {
		name := strings.TrimSuffix(path.Base(src), ".cpp")
		srcs := []string{src}
		if hasBenchMain {
			srcs = append(srcs, cppBenchMain)
		}
		r := rule.NewRule(kindCcBinary, name)
		r.SetAttr("srcs", srcs)
		r.SetAttr("tags", []string{tagCPU})
		r.SetAttr("deps", []string{":" + lib, "@google_benchmark//:benchmark", "@gperftools//:cpu_profiler"})
		out = append(out, r)
	}

	hasShim := len(globWorkloads(args.Dir, "mem", "prof_dump", ".cpp")) > 0
	for _, src := range globWorkloads(args.Dir, "mem", "mem_", ".cpp") {
		name := strings.TrimSuffix(path.Base(src), ".cpp")
		srcs := []string{src}
		if hasShim {
			srcs = append(srcs, cppMemShimSrc, cppMemShimHdr)
		}
		r := rule.NewRule(kindCcBinary, name)
		r.SetAttr("srcs", srcs)
		r.SetAttr("tags", []string{tagMem})
		r.SetAttr("deps", []string{":" + lib, "@gperftools//:tcmalloc"})
		out = append(out, r)
	}
	return out
}

// --- END lang:cpp ---
