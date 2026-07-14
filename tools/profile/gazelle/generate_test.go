package profiling_gazelle

import (
	"os"
	"path"
	"path/filepath"
	"reflect"
	"sort"
	"testing"

	"github.com/bazelbuild/bazel-gazelle/language"
	"github.com/bazelbuild/bazel-gazelle/rule"
)

const libBuild = `
rust_library(
    name = "foo",
    srcs = glob(["src/**/*.rs"]),
)
`

const libWithOrphansBuild = `
rust_library(
    name = "foo",
    srcs = glob(["src/**/*.rs"]),
)

rust_binary(
    name = "bench_gone",
    srcs = ["benches/bench_gone.rs"],
    tags = ["profiling-cpu"],
)

rust_binary(
    name = "bench_handmade",
    srcs = ["handmade.rs"],
)
`

// workloadDir lays out a package directory with one criterion bench,
// one memory workload, and the shared capture shim.
func workloadDir(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	for _, f := range []string{"benches/bench_alpha.rs", "mem/mem_beta.rs", "mem/prof_dump.rs"} {
		p := filepath.Join(dir, f)
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(p, []byte("fn main() {}\n"), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	return dir
}

func parseBuild(t *testing.T, rel, content string) *rule.File {
	t.Helper()
	f, err := rule.LoadData(filepath.Join(rel, "BUILD.bazel"), path.Base(rel), []byte(content))
	if err != nil {
		t.Fatalf("LoadData(%s): %v", rel, err)
	}
	return f
}

func ruleNames(rules []*rule.Rule) []string {
	if len(rules) == 0 {
		return nil
	}
	out := make([]string, 0, len(rules))
	for _, r := range rules {
		out = append(out, r.Name())
	}
	sort.Strings(out)
	return out
}

func assertResult(t *testing.T, res language.GenerateResult, wantGen, wantEmpty []string) {
	t.Helper()
	if got := ruleNames(res.Gen); !reflect.DeepEqual(got, wantGen) {
		t.Errorf("Gen = %v, want %v", got, wantGen)
	}
	if got := ruleNames(res.Empty); !reflect.DeepEqual(got, wantEmpty) {
		t.Errorf("Empty = %v, want %v", got, wantEmpty)
	}
}

func optedIn(rel string) *profilingLang {
	return &profilingLang{optIn: map[string]bool{rel: true}}
}

func TestNotOptedIn_Untouched(t *testing.T) {
	t.Parallel()
	res := (&profilingLang{}).GenerateRules(language.GenerateArgs{
		Dir: workloadDir(t), Rel: "modules/foo",
		File: parseBuild(t, "modules/foo", libWithOrphansBuild),
	})
	assertResult(t, res, nil, nil)
}

func TestOptIn_GeneratesBenchAndMem(t *testing.T) {
	t.Parallel()
	res := optedIn("modules/foo").GenerateRules(language.GenerateArgs{
		Dir: workloadDir(t), Rel: "modules/foo",
		File: parseBuild(t, "modules/foo", libBuild),
	})
	assertResult(t, res, []string{"bench_alpha", "mem_beta"}, nil)

	for _, r := range res.Gen {
		switch r.Name() {
		case "bench_alpha":
			if got := r.AttrStrings("tags"); !reflect.DeepEqual(got, []string{tagCPU}) {
				t.Errorf("bench tags = %v", got)
			}
			want := []string{":foo", "@crates//:criterion", "@crates//:pprof"}
			if got := r.AttrStrings("deps"); !reflect.DeepEqual(got, want) {
				t.Errorf("bench deps = %v, want %v", got, want)
			}
		case "mem_beta":
			if got := r.AttrString("crate_root"); got != "mem/mem_beta.rs" {
				t.Errorf("mem crate_root = %q", got)
			}
			wantSrcs := []string{"mem/mem_beta.rs", memShim}
			if got := r.AttrStrings("srcs"); !reflect.DeepEqual(got, wantSrcs) {
				t.Errorf("mem srcs = %v, want %v", got, wantSrcs)
			}
			if got := r.AttrStrings("target_compatible_with"); !reflect.DeepEqual(got, []string{"@platforms//os:linux"}) {
				t.Errorf("mem target_compatible_with = %v", got)
			}
		}
	}
}

func TestOptIn_ReapsOrphansButNotHandmade(t *testing.T) {
	t.Parallel()
	// bench_gone is tagged and has no source file left -> reaped;
	// bench_handmade carries no profiling tag -> never touched.
	res := optedIn("modules/foo").GenerateRules(language.GenerateArgs{
		Dir: t.TempDir(), Rel: "modules/foo",
		File: parseBuild(t, "modules/foo", libWithOrphansBuild),
	})
	assertResult(t, res, nil, []string{"bench_gone"})
}

func TestRemoveAll_ReapsGenerated(t *testing.T) {
	t.Parallel()
	p := optedIn("modules/foo")
	p.removeAll = true
	res := p.GenerateRules(language.GenerateArgs{
		Dir: workloadDir(t), Rel: "modules/foo",
		File: parseBuild(t, "modules/foo", libWithOrphansBuild),
	})
	assertResult(t, res, nil, []string{"bench_gone"})
}

func TestOptIn_NoCanonicalLibrary_GeneratesNothing(t *testing.T) {
	t.Parallel()
	res := optedIn("modules/foo").GenerateRules(language.GenerateArgs{
		Dir: workloadDir(t), Rel: "modules/foo",
		File: parseBuild(t, "modules/foo", "# empty\n"),
	})
	assertResult(t, res, nil, nil)
}

// --- BEGIN lang:cpp ---
const cppLibBuild = `
cc_library(
    name = "foo",
    srcs = glob(["src/**/*.cpp"]),
)
`

// cppWorkloadDir lays out a package directory with one google/benchmark
// bench, one memory workload, and the shared entrypoint/shim sources.
func cppWorkloadDir(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	files := []string{
		"benches/bench_alpha.cpp",
		"benches/prof_main.cpp",
		"mem/mem_beta.cpp",
		"mem/prof_dump.cpp",
		"mem/prof_dump.h",
	}
	for _, f := range files {
		p := filepath.Join(dir, f)
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(p, []byte("// workload\n"), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	return dir
}

func TestOptIn_GeneratesCppBenchAndMem(t *testing.T) {
	t.Parallel()
	res := optedIn("modules/foo").GenerateRules(language.GenerateArgs{
		Dir: cppWorkloadDir(t), Rel: "modules/foo",
		File: parseBuild(t, "modules/foo", cppLibBuild),
	})
	assertResult(t, res, []string{"bench_alpha", "mem_beta"}, nil)

	for _, r := range res.Gen {
		switch r.Name() {
		case "bench_alpha":
			if got := r.AttrStrings("tags"); !reflect.DeepEqual(got, []string{tagCPU}) {
				t.Errorf("bench tags = %v", got)
			}
			wantSrcs := []string{"benches/bench_alpha.cpp", cppBenchMain}
			if got := r.AttrStrings("srcs"); !reflect.DeepEqual(got, wantSrcs) {
				t.Errorf("bench srcs = %v, want %v", got, wantSrcs)
			}
			want := []string{":foo", "@google_benchmark//:benchmark", "@gperftools//:cpu_profiler"}
			if got := r.AttrStrings("deps"); !reflect.DeepEqual(got, want) {
				t.Errorf("bench deps = %v, want %v", got, want)
			}
		case "mem_beta":
			if got := r.AttrStrings("tags"); !reflect.DeepEqual(got, []string{tagMem}) {
				t.Errorf("mem tags = %v", got)
			}
			wantSrcs := []string{"mem/mem_beta.cpp", cppMemShimSrc, cppMemShimHdr}
			if got := r.AttrStrings("srcs"); !reflect.DeepEqual(got, wantSrcs) {
				t.Errorf("mem srcs = %v, want %v", got, wantSrcs)
			}
			want := []string{":foo", "@gperftools//:tcmalloc"}
			if got := r.AttrStrings("deps"); !reflect.DeepEqual(got, want) {
				t.Errorf("mem deps = %v, want %v", got, want)
			}
		}
	}
}

// --- END lang:cpp ---

// --- BEGIN lang:python ---
const pyLibBuild = `
py_library(
    name = "foo",
    srcs = glob(["src/**/*.py"]),
)
`

// pyWorkloadDir lays out a package directory with one pytest-benchmark
// bench, one memory workload, and the shared harness/shim sources.
func pyWorkloadDir(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	files := []string{
		"benches/bench_alpha.py",
		"benches/conftest.py",
		"benches/pytest_main.py",
		"mem/mem_beta.py",
		"mem/prof_dump.py",
	}
	for _, f := range files {
		p := filepath.Join(dir, f)
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(p, []byte("# workload\n"), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	return dir
}

func TestOptIn_GeneratesPythonBenchAndMem(t *testing.T) {
	t.Parallel()
	res := optedIn("modules/foo").GenerateRules(language.GenerateArgs{
		Dir: pyWorkloadDir(t), Rel: "modules/foo",
		File: parseBuild(t, "modules/foo", pyLibBuild),
	})
	assertResult(t, res, []string{"bench_alpha", "mem_beta"}, nil)

	for _, r := range res.Gen {
		switch r.Name() {
		case "bench_alpha":
			if got := r.Kind(); got != kindPyTest {
				t.Errorf("bench kind = %v", got)
			}
			wantSrcs := []string{"benches/bench_alpha.py", pyBenchShim, pyBenchMain}
			if got := r.AttrStrings("srcs"); !reflect.DeepEqual(got, wantSrcs) {
				t.Errorf("bench srcs = %v, want %v", got, wantSrcs)
			}
			if got := r.AttrString("main"); got != pyBenchMain {
				t.Errorf("bench main = %q", got)
			}
			if got := r.AttrStrings("args"); !reflect.DeepEqual(got, []string{"--benchmark-disable"}) {
				t.Errorf("bench args = %v", got)
			}
			want := []string{":foo", pyDepPyinstrument, pyDepPytest, pyDepPytestBenchmark}
			if got := r.AttrStrings("deps"); !reflect.DeepEqual(got, want) {
				t.Errorf("bench deps = %v, want %v", got, want)
			}
		case "mem_beta":
			if got := r.Kind(); got != kindPyBinary {
				t.Errorf("mem kind = %v", got)
			}
			wantSrcs := []string{"mem/mem_beta.py", pyMemShim}
			if got := r.AttrStrings("srcs"); !reflect.DeepEqual(got, wantSrcs) {
				t.Errorf("mem srcs = %v, want %v", got, wantSrcs)
			}
			if got := r.AttrString("main"); got != "mem/mem_beta.py" {
				t.Errorf("mem main = %q", got)
			}
			want := []string{":foo", pyDepMemray}
			if got := r.AttrStrings("deps"); !reflect.DeepEqual(got, want) {
				t.Errorf("mem deps = %v, want %v", got, want)
			}
		}
	}
}

// --- END lang:python ---

// --- BEGIN lang:java ---
const javaLibBuild = `
java_library(
    name = "foo",
    srcs = glob(["src/**/*.java"]),
)
`

// javaWorkloadDir lays out a package directory with one JMH bench, one
// memory workload (with a package declaration for main_class), and the
// shared capture shim.
func javaWorkloadDir(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	files := map[string]string{
		"benches/BenchAlpha.java": "package monorepo.foo;\n",
		"mem/MemBeta.java":        "package monorepo.foo;\n",
		"mem/ProfDump.java":       "package monorepo.foo;\n",
	}
	for f, content := range files {
		p := filepath.Join(dir, f)
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(p, []byte(content), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	return dir
}

func TestJavaTargetNamesKeepReaperPrefix(t *testing.T) {
	t.Parallel()
	// The want values all carry the bench_/mem_ prefix the reaper's
	// ownership contract requires, even for class names where plain
	// snake-casing would lose it (Benchmark, Bench2D).
	benchCases := map[string]string{
		"benches/BenchMatmul.java":  "bench_matmul",
		"benches/Benchmark.java":    "bench_mark",
		"benches/Bench2D.java":      "bench_2_d",
		"benches/BenchHTTPGet.java": "bench_h_t_t_p_get",
	}
	for src, want := range benchCases {
		if got := javaTargetName("bench_", "Bench", src); got != want {
			t.Errorf("javaTargetName(bench_, %q) = %q, want %q", src, got, want)
		}
	}
	memCases := map[string]string{
		"mem/MemRetainedGrowth.java": "mem_retained_growth",
		"mem/Mem2Pools.java":         "mem_2_pools",
	}
	for src, want := range memCases {
		if got := javaTargetName("mem_", "Mem", src); got != want {
			t.Errorf("javaTargetName(mem_, %q) = %q, want %q", src, got, want)
		}
	}
}

func TestOptIn_GeneratesJavaBenchAndMem(t *testing.T) {
	t.Parallel()
	res := optedIn("modules/foo").GenerateRules(language.GenerateArgs{
		Dir: javaWorkloadDir(t), Rel: "modules/foo",
		File: parseBuild(t, "modules/foo", javaLibBuild),
	})
	assertResult(t, res, []string{"bench_alpha", "mem_beta"}, nil)

	for _, r := range res.Gen {
		switch r.Name() {
		case "bench_alpha":
			wantSrcs := []string{"benches/BenchAlpha.java"}
			if got := r.AttrStrings("srcs"); !reflect.DeepEqual(got, wantSrcs) {
				t.Errorf("bench srcs = %v, want %v", got, wantSrcs)
			}
			if got := r.AttrStrings("tags"); !reflect.DeepEqual(got, []string{"no-lint", tagCPU}) {
				t.Errorf("bench tags = %v", got)
			}
			if got := r.AttrString("main_class"); got != javaJmhMain {
				t.Errorf("bench main_class = %q", got)
			}
			if got := r.AttrStrings("plugins"); !reflect.DeepEqual(got, []string{javaJmhPlugin}) {
				t.Errorf("bench plugins = %v", got)
			}
			want := []string{":foo", javaDepJmhCore}
			if got := r.AttrStrings("deps"); !reflect.DeepEqual(got, want) {
				t.Errorf("bench deps = %v, want %v", got, want)
			}
		case "mem_beta":
			wantSrcs := []string{"mem/MemBeta.java", javaMemShim}
			if got := r.AttrStrings("srcs"); !reflect.DeepEqual(got, wantSrcs) {
				t.Errorf("mem srcs = %v, want %v", got, wantSrcs)
			}
			if got := r.AttrString("main_class"); got != "monorepo.foo.MemBeta" {
				t.Errorf("mem main_class = %q", got)
			}
			want := []string{":foo"}
			if got := r.AttrStrings("deps"); !reflect.DeepEqual(got, want) {
				t.Errorf("mem deps = %v, want %v", got, want)
			}
		}
	}
}

// --- END lang:java ---
