// Package lint_gazelle is a Gazelle language extension that
// auto-generates lint_test targets for packages in this monorepo,
// driven by the source-rule kind of each package's canonical target.
//
// Each linter's lint_test factory lives in //tools/lint:linters.bzl
// (clang_tidy_test, clippy_test, pmd_test, spotbugs_test, ruff_test).
// This extension emits one or more *_test targets per package based on
// the source-rule kinds present, tagging each with "lint" so CI can
// select them via --test_tag_filters=lint.
//
// Skeleton state: the extension compiles and registers with gazelle
// but emits no rules yet. Per-language generators in cpp.go, rust.go,
// java.go, python.go are stubs returning nil; they will be fleshed out
// one language at a time as Phase B progresses.
package lint_gazelle

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
	extName = "lint"

	// directiveIgnore is the per-package opt-out. A BUILD file carrying
	// `# gazelle:lint_ignore` is excluded from lint_test generation
	// regardless of which source rule kinds it contains. Existing
	// lint_test rules in such a package are reaped on the next run. The
	// directive string is owned by //tools/gazelle/directives so the
	// vocab extension can advertise it to sibling generators' binaries.
	directiveIgnore = directives.LintIgnore

	// directiveKeep is the per-package freeze. A BUILD file carrying
	// `# gazelle:lint_ignore_keep` is left exactly as written: lint_gen
	// neither generates new lint_test rules nor reaps existing ones.
	// Used to hand-gate generated rules (e.g. wrapping them in
	// feature:lint section markers in a shipped BUILD file) without
	// gazelle clobbering them on regen.
	directiveKeep = directives.LintIgnoreKeep

	// tagSkip is the per-target opt-out. A source rule (py_library,
	// cc_binary, etc.) carrying `tags = ["no-lint"]` is skipped by every
	// per-language generator, so no lint_test sibling is emitted for it.
	tagSkip = "no-lint"

	// flagRemove is the global removal switch. `-lint_remove` makes the
	// extension generate nothing in every package, so computeEmpty reaps
	// all owned lint_test rules repo-wide. The bootstrap tool runs
	// `bazel run //:lint_gen -- -lint_remove` to strip lint targets from a
	// target repo when the lint feature is dropped on re-bootstrap, before
	// the extension's own tool directory is pruned.
	flagRemove = "lint_remove"
)

// lintLang holds per-run state shared between Language-interface
// callbacks. ignored accumulates packages opted out via the
// lint_ignore directive; keep accumulates packages frozen via the
// lint_ignore_keep directive; both are populated across Configure
// calls before GenerateRules consumes them. removeAll is bound to the
// -lint_remove flag and, when set, suppresses generation everywhere so
// existing rules are reaped.
type lintLang struct {
	ignored   map[string]bool
	keep      map[string]bool
	removeAll bool
}

// NewLanguage is the entrypoint gazelle_binary calls to obtain an
// instance of this extension.
func NewLanguage() language.Language { return &lintLang{} }

func (*lintLang) Name() string { return extName }

func (*lintLang) Kinds() map[string]rule.KindInfo { return lintKinds }

func (*lintLang) Loads() []rule.LoadInfo { return lintLoads }

// GenerateRules is implemented in generate.go.

func (*lintLang) Fix(c *config.Config, f *rule.File) {}

func (p *lintLang) RegisterFlags(fs *flag.FlagSet, cmd string, c *config.Config) {
	fs.BoolVar(&p.removeAll, flagRemove, false,
		"remove all generated lint_test rules instead of generating them (used when the lint feature is dropped)")
}

func (*lintLang) CheckFlags(fs *flag.FlagSet, c *config.Config) error { return nil }

func (*lintLang) KnownDirectives() []string { return []string{directiveIgnore, directiveKeep} }

// Configure records any # gazelle:lint_ignore or
// # gazelle:lint_ignore_keep directive so that GenerateRules can
// short-circuit the affected packages — ignore reaps existing rules,
// keep freezes them. Called once per package as gazelle walks the tree.
func (p *lintLang) Configure(c *config.Config, rel string, f *rule.File) {
	if f == nil {
		return
	}
	for _, d := range f.Directives {
		switch d.Key {
		case directiveIgnore:
			if p.ignored == nil {
				p.ignored = map[string]bool{}
			}
			p.ignored[rel] = true
		case directiveKeep:
			if p.keep == nil {
				p.keep = map[string]bool{}
			}
			p.keep[rel] = true
		}
	}
}

func (*lintLang) Imports(c *config.Config, r *rule.Rule, f *rule.File) []resolve.ImportSpec {
	return nil
}

func (*lintLang) Embeds(r *rule.Rule, from label.Label) []label.Label { return nil }

func (*lintLang) Resolve(c *config.Config, ix *resolve.RuleIndex, rc *repo.RemoteCache, r *rule.Rule, imports interface{}, from label.Label) {
}

// hasSkipTag reports whether r carries `tags = ["no-lint"]` (or any
// tag list that includes "no-lint"). Per-language generators call
// this to honour the per-target opt-out.
func hasSkipTag(r *rule.Rule) bool {
	for _, t := range r.AttrStrings("tags") {
		if t == tagSkip {
			return true
		}
	}
	return false
}

// newLintRule constructs a generated lint_test rule with the standard
// attribute set: srcs pointing at the source rule, tags = ["lint"]
// for --test_tag_filters selection, and size = "small" so Bazel
// schedules the test densely and gives it the 60s timeout that
// matches lint runtimes (lints are uniformly fast under normal Bazel
// caching). Per-language generators dispatch their kind + name
// suffix; everything else is uniform.
func newLintRule(srcName, kind, nameSuffix string) *rule.Rule {
	t := rule.NewRule(kind, srcName+nameSuffix)
	t.SetAttr("srcs", []string{":" + srcName})
	t.SetAttr("tags", []string{"lint"})
	t.SetAttr("size", "small")
	return t
}
