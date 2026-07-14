package profiling_gazelle

import (
	"path"
	"path/filepath"
	"strings"

	"github.com/bazelbuild/bazel-gazelle/language"
	"github.com/bazelbuild/bazel-gazelle/rule"
)

// GenerateRules emits workload targets for packages that carry the
// # gazelle:profiling directive, dispatching to per-language generators
// that map workload source files to runner-discoverable targets. All
// other packages return an empty result — no generation, no reaping —
// so hand-written bench targets elsewhere are never touched, and the
// BUILD-less benches/ and mem/ subdirectories themselves never sprout
// BUILD files.
//
// Within an opted-in package, any pre-existing rule that looks
// generated (bench_/mem_ name prefix plus a profiling tag) but is no
// longer in the generated set is added to Empty so gazelle deletes it —
// that reaps orphans from source-file deletions and renames. Removing
// the directive itself orphans the rules instead; delete them by hand
// or re-add the directive and remove the source files.
//
// Under -profiling_remove (p.removeAll) generation is suppressed in
// opted-in packages, so the reaper strips every generated workload rule
// repo-wide — the feature teardown the bootstrap tool runs when
// profiling is dropped.
func (p *profilingLang) GenerateRules(args language.GenerateArgs) language.GenerateResult {
	if !p.optIn[args.Rel] {
		return language.GenerateResult{}
	}

	var rules []*rule.Rule
	if !p.removeAll {
		// --- BEGIN lang:rust ---
		rules = append(rules, generateRustWorkloads(args)...)
		// --- END lang:rust ---
		// --- BEGIN lang:go ---
		rules = append(rules, generateGoWorkloads(args)...)
		// --- END lang:go ---
		// --- BEGIN lang:cpp ---
		rules = append(rules, generateCppWorkloads(args)...)
		// --- END lang:cpp ---
		// --- BEGIN lang:python ---
		rules = append(rules, generatePythonWorkloads(args)...)
		// --- END lang:python ---
		// --- BEGIN lang:java ---
		rules = append(rules, generateJavaWorkloads(args)...)
		// --- END lang:java ---
	}

	imports := make([]interface{}, len(rules))
	return language.GenerateResult{
		Gen:     rules,
		Imports: imports,
		Empty:   computeEmpty(args, rules),
	}
}

// reapKinds is every rule kind any language's generator may ever have
// emitted, as literal strings and deliberately NOT gated by lang markers
// (unlike profilingKinds): a scaffold that drops a language after
// generating its workloads must still recognize the leftover rules for
// deletion, or they dangle against the language's pruned dependencies.
var reapKinds = map[string]bool{
	"cc_binary":   true,
	"go_binary":   true,
	"go_test":     true,
	"java_binary": true,
	"py_binary":   true,
	"py_test":     true,
	"rust_binary": true,
}

// computeEmpty walks the existing BUILD for generated-looking workload
// rules and returns those whose names are not in the regenerated set,
// for gazelle to delete. Ownership is name prefix + profiling tag, not
// kind: the extension emits general-purpose kinds, so reaping by kind
// alone would delete unrelated binaries.
func computeEmpty(args language.GenerateArgs, generated []*rule.Rule) []*rule.Rule {
	if args.File == nil {
		return nil
	}
	keep := make(map[string]bool, len(generated))
	for _, r := range generated {
		keep[r.Name()] = true
	}
	var empty []*rule.Rule
	for _, r := range args.File.Rules {
		if !reapKinds[r.Kind()] {
			continue
		}
		if !looksGenerated(r) || keep[r.Name()] {
			continue
		}
		empty = append(empty, rule.NewRule(r.Kind(), r.Name()))
	}
	return empty
}

func looksGenerated(r *rule.Rule) bool {
	if !strings.HasPrefix(r.Name(), "bench_") && !strings.HasPrefix(r.Name(), "mem_") {
		return false
	}
	for _, t := range r.AttrStrings("tags") {
		if t == tagCPU || t == tagMem {
			return true
		}
	}
	return false
}

// globWorkloads returns package-relative paths of
// <subdir>/<prefix>*<suffix>, in sorted order (filepath.Glob sorts).
func globWorkloads(dir, subdir, prefix, suffix string) []string {
	matches, err := filepath.Glob(filepath.Join(dir, subdir, prefix+"*"+suffix))
	if err != nil {
		return nil
	}
	out := make([]string, 0, len(matches))
	for _, m := range matches {
		out = append(out, path.Join(subdir, filepath.Base(m)))
	}
	return out
}

func hasRule(args language.GenerateArgs, name string) bool {
	if args.File == nil {
		return false
	}
	for _, r := range args.File.Rules {
		if r.Name() == name {
			return true
		}
	}
	return false
}
