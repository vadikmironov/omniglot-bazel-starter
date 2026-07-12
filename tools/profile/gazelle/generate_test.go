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
