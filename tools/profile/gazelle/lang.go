// Package profiling_gazelle is a Gazelle language extension that
// generates tagged profiling workload targets for packages that opt in
// with the # gazelle:profiling directive.
//
// In an opted-in package, per-language generators map workload source
// files to runner-discoverable targets: criterion bench sources under
// benches/ become bench_* binaries tagged "profiling-cpu", and one-shot
// memory workload sources under mem/ become mem_* binaries tagged
// "profiling-mem". Packages without the directive are never touched —
// unlike lint_gen's repo-wide opt-out model, workload generation is
// strictly opt-in, and hand-written targets elsewhere stay untouched.
package profiling_gazelle

import (
	"flag"

	"github.com/bazelbuild/bazel-gazelle/config"
	"github.com/bazelbuild/bazel-gazelle/label"
	"github.com/bazelbuild/bazel-gazelle/language"
	"github.com/bazelbuild/bazel-gazelle/repo"
	"github.com/bazelbuild/bazel-gazelle/resolve"
	"github.com/bazelbuild/bazel-gazelle/rule"

	"omniglot-bazel-starter/tools/gazelle/directives"
)

const (
	extName = "profiling"

	// directiveOptIn is the per-package opt-in. A BUILD file carrying
	// `# gazelle:profiling` gets workload targets generated from its
	// benches/ and mem/ sources; orphaned generated rules (source file
	// deleted or renamed) are reaped on the next run. The directive
	// string is owned by //tools/gazelle/directives so the vocab
	// extension can advertise it to sibling generators' binaries.
	directiveOptIn = directives.Profiling

	// flagRemove is the global removal switch. `-profiling_remove` reaps
	// every generated workload rule in opted-in packages repo-wide. The
	// bootstrap tool runs `bazel run //:profile_gen -- -profiling_remove`
	// when the profiling feature is dropped on re-bootstrap, before the
	// feature's crate deps (criterion, pprof, jemalloc) are pruned.
	flagRemove = "profiling_remove"
)

// profilingLang holds per-run state shared between Language-interface
// callbacks. optIn accumulates packages that carry the profiling
// directive, populated across Configure calls before GenerateRules
// consumes it. removeAll is bound to the -profiling_remove flag and,
// when set, suppresses generation so existing rules are reaped.
type profilingLang struct {
	optIn     map[string]bool
	removeAll bool
}

// NewLanguage is the entrypoint gazelle_binary calls to obtain an
// instance of this extension.
func NewLanguage() language.Language { return &profilingLang{} }

func (*profilingLang) Name() string { return extName }

func (*profilingLang) Kinds() map[string]rule.KindInfo { return profilingKinds }

func (*profilingLang) Loads() []rule.LoadInfo { return profilingLoads }

// GenerateRules is implemented in generate.go.

func (*profilingLang) Fix(c *config.Config, f *rule.File) {}

func (p *profilingLang) RegisterFlags(fs *flag.FlagSet, cmd string, c *config.Config) {
	fs.BoolVar(&p.removeAll, flagRemove, false,
		"remove all generated workload rules instead of generating them (used when the profiling feature is dropped)")
}

func (*profilingLang) CheckFlags(fs *flag.FlagSet, c *config.Config) error { return nil }

func (*profilingLang) KnownDirectives() []string { return []string{directiveOptIn} }

// Configure records any # gazelle:profiling directive so GenerateRules
// knows which packages opted in. Called once per package as gazelle
// walks the tree.
func (p *profilingLang) Configure(c *config.Config, rel string, f *rule.File) {
	if f == nil {
		return
	}
	for _, d := range f.Directives {
		if d.Key == directiveOptIn {
			if p.optIn == nil {
				p.optIn = map[string]bool{}
			}
			p.optIn[rel] = true
		}
	}
}

func (*profilingLang) Imports(c *config.Config, r *rule.Rule, f *rule.File) []resolve.ImportSpec {
	return nil
}

func (*profilingLang) Embeds(r *rule.Rule, from label.Label) []label.Label { return nil }

func (*profilingLang) Resolve(c *config.Config, ix *resolve.RuleIndex, rc *repo.RemoteCache, r *rule.Rule, imports interface{}, from label.Label) {
}
