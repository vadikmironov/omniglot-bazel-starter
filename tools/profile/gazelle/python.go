package profiling_gazelle

// --- BEGIN lang:python ---
import (
	"path"
	"strings"

	"github.com/bazelbuild/bazel-gazelle/language"
	"github.com/bazelbuild/bazel-gazelle/rule"
)

// pyBenchMain and pyBenchShim form the shared bench harness compiled into
// every CPU bench target: pytest on the target's bench directory, with a
// conftest that runs the session under pyinstrument and writes folded
// stacks. pyMemShim is the memray capture shim for memory workloads.
const (
	pyBenchMain = "benches/pytest_main.py"
	pyBenchShim = "benches/conftest.py"
	pyMemShim   = "mem/prof_dump.py"
)

// Hub-repo labels of the capture dependencies (the literal form
// requirement() resolves to, so generated rules converge byte-for-byte).
const (
	pyDepPytest          = "@omniglot-bazel-starter_pip_dependencies//pytest:pkg"
	pyDepPytestBenchmark = "@omniglot-bazel-starter_pip_dependencies//pytest_benchmark:pkg"
	pyDepPyinstrument    = "@omniglot-bazel-starter_pip_dependencies//pyinstrument:pkg"
	pyDepMemray          = "@omniglot-bazel-starter_pip_dependencies//memray:pkg"
)

// generatePythonWorkloads maps the package's Python workload sources to
// runner-discoverable targets:
//
//	benches/bench_<x>.py -> py_test(bench_<x>)   pytest-benchmark + pyinstrument
//	                                             session capture, tagged profiling-cpu
//	mem/mem_<x>.py       -> py_binary(mem_<x>)   memray live-heap capture, tagged profiling-mem
//
// Bench targets default to --benchmark-disable so `bazel test` runs them
// as one-pass smoke tests; the runner re-enables benchmarking. Each
// target depends on the package's canonical library (the rule named
// after the package basename); if that rule is absent nothing is
// generated.
func generatePythonWorkloads(args language.GenerateArgs) []*rule.Rule {
	lib := path.Base(args.Rel)
	if args.Rel == "" || !hasRule(args, lib) {
		return nil
	}

	var out []*rule.Rule
	// Benches need the shared pytest entrypoint as their main; without it
	// nothing is generated (a main outside srcs would not analyze).
	hasBenchMain := len(globWorkloads(args.Dir, "benches", "pytest_main", ".py")) > 0
	hasBenchShim := len(globWorkloads(args.Dir, "benches", "conftest", ".py")) > 0
	if hasBenchMain {
		for _, src := range globWorkloads(args.Dir, "benches", "bench_", ".py") {
			name := strings.TrimSuffix(path.Base(src), ".py")
			srcs := []string{src}
			if hasBenchShim {
				srcs = append(srcs, pyBenchShim)
			}
			srcs = append(srcs, pyBenchMain)
			r := rule.NewRule(kindPyTest, name)
			r.SetAttr("size", "medium")
			r.SetAttr("srcs", srcs)
			r.SetAttr("args", []string{"--benchmark-disable"})
			r.SetAttr("main", pyBenchMain)
			r.SetAttr("tags", []string{tagCPU})
			r.SetAttr("deps", []string{":" + lib, pyDepPyinstrument, pyDepPytest, pyDepPytestBenchmark})
			out = append(out, r)
		}
	}

	hasShim := len(globWorkloads(args.Dir, "mem", "prof_dump", ".py")) > 0
	for _, src := range globWorkloads(args.Dir, "mem", "mem_", ".py") {
		name := strings.TrimSuffix(path.Base(src), ".py")
		srcs := []string{src}
		if hasShim {
			srcs = append(srcs, pyMemShim)
		}
		r := rule.NewRule(kindPyBinary, name)
		r.SetAttr("srcs", srcs)
		r.SetAttr("imports", []string{"mem"})
		r.SetAttr("main", src)
		r.SetAttr("tags", []string{tagMem})
		r.SetAttr("deps", []string{":" + lib, pyDepMemray})
		out = append(out, r)
	}
	return out
}

// --- END lang:python ---
