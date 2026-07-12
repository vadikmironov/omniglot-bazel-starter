package profiling_gazelle

// --- BEGIN lang:go ---
import (
	"path"
	"strings"

	"github.com/bazelbuild/bazel-gazelle/language"
	"github.com/bazelbuild/bazel-gazelle/rule"
)

// goMemShim is the shared capture shim compiled into every Go memory
// workload binary (runtime heap profile dumped as pprof).
const goMemShim = "mem/prof_dump.go"

// generateGoWorkloads maps the package's Go workload sources to
// runner-discoverable targets:
//
//	benches/bench_<x>_test.go -> go_test(bench_<x>)  testing.B benches, tagged profiling-cpu
//	mem/mem_<x>.go            -> go_binary(mem_<x>)  runtime/pprof heap capture, tagged profiling-mem
//
// Benches embed the package's canonical library (same-package testing.B
// functions); memory binaries import it as a dep. If the canonical rule
// is absent nothing is generated.
func generateGoWorkloads(args language.GenerateArgs) []*rule.Rule {
	lib := path.Base(args.Rel)
	if args.Rel == "" || !hasRule(args, lib) {
		return nil
	}

	var out []*rule.Rule
	for _, src := range globWorkloads(args.Dir, "benches", "bench_", "_test.go") {
		name := strings.TrimSuffix(path.Base(src), "_test.go")
		r := rule.NewRule(kindGoTest, name)
		r.SetAttr("srcs", []string{src})
		r.SetAttr("embed", []string{":" + lib})
		r.SetAttr("tags", []string{tagCPU})
		out = append(out, r)
	}

	hasShim := len(globWorkloads(args.Dir, "mem", "prof_dump", ".go")) > 0
	for _, src := range globWorkloads(args.Dir, "mem", "mem_", ".go") {
		name := strings.TrimSuffix(path.Base(src), ".go")
		srcs := []string{src}
		if hasShim {
			srcs = append(srcs, goMemShim)
		}
		r := rule.NewRule(kindGoBinary, name)
		r.SetAttr("srcs", srcs)
		r.SetAttr("tags", []string{tagMem})
		r.SetAttr("deps", []string{":" + lib})
		out = append(out, r)
	}
	return out
}

// --- END lang:go ---
