package profiling_gazelle

// --- BEGIN lang:java ---
import (
	"os"
	"path"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/bazelbuild/bazel-gazelle/language"
	"github.com/bazelbuild/bazel-gazelle/rule"
)

// javaMemShim is the shared capture shim compiled into every memory
// workload binary (a JFR recording of weighted allocation samples dumped
// via the Recording API). Bench targets get the JMH harness instead:
// org.openjdk.jmh.Main plus the annotation processor plugin.
const (
	javaMemShim      = "mem/ProfDump.java"
	javaJmhMain      = "org.openjdk.jmh.Main"
	javaJmhPlugin    = "//tools/profile:jmh_annprocess"
	javaDepJmhCore   = "@omniglot-bazel-starter_maven_dependencies//:org_openjdk_jmh_jmh_core"
	javaPackageRegex = `(?m)^package\s+([\w.]+)\s*;`
)

var javaPackagePattern = regexp.MustCompile(javaPackageRegex)

// generateJavaWorkloads maps the package's Java workload sources to
// runner-discoverable targets:
//
//	benches/Bench<X>.java -> java_binary(bench_<x>)  JMH benches, tagged profiling-cpu
//	mem/Mem<X>.java       -> java_binary(mem_<x>)    JFR alloc capture, tagged profiling-mem
//
// Target names are the bench_/mem_ prefix plus the snake_case remainder
// of the class name (BenchMatmul -> bench_matmul), keeping the reaper's
// naming contract while sources follow Java's CamelCase convention.
// Each target depends on the package's canonical
// library (the rule named after the package basename); if that rule is
// absent nothing is generated.
func generateJavaWorkloads(args language.GenerateArgs) []*rule.Rule {
	lib := path.Base(args.Rel)
	if args.Rel == "" || !hasRule(args, lib) {
		return nil
	}

	var out []*rule.Rule
	for _, src := range globWorkloads(args.Dir, "benches", "Bench", ".java") {
		r := rule.NewRule(kindJavaBinary, javaTargetName("bench_", "Bench", src))
		r.SetAttr("srcs", []string{src})
		r.SetAttr("main_class", javaJmhMain)
		r.SetAttr("plugins", []string{javaJmhPlugin})
		// no-lint: PMD/spotbugs would fire on JMH's generated harness
		// (deliberate padding fields, dead stores), not the bench source.
		r.SetAttr("tags", []string{"no-lint", tagCPU})
		r.SetAttr("deps", []string{":" + lib, javaDepJmhCore})
		out = append(out, r)
	}

	hasShim := len(globWorkloads(args.Dir, "mem", "ProfDump", ".java")) > 0
	for _, src := range globWorkloads(args.Dir, "mem", "Mem", ".java") {
		class := javaClassName(src)
		srcs := []string{src}
		if hasShim {
			srcs = append(srcs, javaMemShim)
		}
		r := rule.NewRule(kindJavaBinary, javaTargetName("mem_", "Mem", src))
		r.SetAttr("srcs", srcs)
		r.SetAttr("main_class", javaMainClass(args.Dir, src, class))
		r.SetAttr("tags", []string{tagMem})
		r.SetAttr("deps", []string{":" + lib})
		out = append(out, r)
	}
	return out
}

func javaClassName(src string) string {
	return strings.TrimSuffix(path.Base(src), ".java")
}

// javaTargetName builds the target name with the bench_/mem_ prefix by
// construction: the reaper's ownership contract keys on that prefix, and
// snake-casing the class name alone can lose it (Benchmark -> benchmark,
// Bench2D -> bench2_d).
func javaTargetName(prefix, classPrefix, src string) string {
	return prefix + camelToSnake(strings.TrimPrefix(javaClassName(src), classPrefix))
}

// javaMainClass qualifies the workload's class with the package declared
// in its source file (a bare class name if the declaration is missing).
func javaMainClass(dir, src, class string) string {
	content, err := os.ReadFile(filepath.Join(dir, filepath.FromSlash(src)))
	if err != nil {
		return class
	}
	m := javaPackagePattern.FindSubmatch(content)
	if m == nil {
		return class
	}
	return string(m[1]) + "." + class
}

// camelToSnake lowercases a CamelCase name with underscore separators:
// RetainedGrowth -> retained_growth.
func camelToSnake(name string) string {
	var b strings.Builder
	for i, r := range name {
		if r >= 'A' && r <= 'Z' {
			if i > 0 {
				b.WriteByte('_')
			}
			r += 'a' - 'A'
		}
		b.WriteRune(r)
	}
	return b.String()
}

// --- END lang:java ---
