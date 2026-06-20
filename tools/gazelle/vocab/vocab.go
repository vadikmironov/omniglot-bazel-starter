// Package vocab is a generation-free Gazelle language extension whose
// sole purpose is to widen a gazelle_binary's recognised directive set
// to the repo-wide vocabulary (//tools/gazelle/directives).
//
// Gazelle validates each `# gazelle:X` directive against the union of
// KnownDirectives() over the languages loaded into the running binary.
// Each generator's binary loads only its own feature extension, so
// without vocab, publish_gen warns on lint_* directives and lint_gen
// warns on publish_* directives. Adding vocab to every gazelle_binary's
// `languages` registers directives.All() into that union, so each binary
// recognises sibling generators' directives without having to understand
// or act on them.
//
// vocab owns no kinds, emits no rules, registers no flags, and resolves
// no imports. Every Language callback below is an intentional noop except
// KnownDirectives — vocab contributes vocabulary, not behaviour. That is
// what makes it safe to load into any binary: it can never generate or
// reap a rule, so it cannot interfere with the binary's real extension.
package vocab

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

const extName = "vocab"

type vocabLang struct{}

// NewLanguage is the entrypoint gazelle_binary calls to obtain an
// instance of this extension.
func NewLanguage() language.Language { return &vocabLang{} }

func (*vocabLang) Name() string { return extName }

// KnownDirectives is the one method that does real work: it advertises
// the repo-wide directive vocabulary so the host binary stops warning on
// directives owned by sibling generators.
func (*vocabLang) KnownDirectives() []string { return directives.All() }

// --- Intentional noops: vocab contributes vocabulary, not behaviour. ---

func (*vocabLang) RegisterFlags(fs *flag.FlagSet, cmd string, c *config.Config) {}

func (*vocabLang) CheckFlags(fs *flag.FlagSet, c *config.Config) error { return nil }

func (*vocabLang) Configure(c *config.Config, rel string, f *rule.File) {}

func (*vocabLang) Kinds() map[string]rule.KindInfo { return nil }

func (*vocabLang) Loads() []rule.LoadInfo { return nil }

func (*vocabLang) Fix(c *config.Config, f *rule.File) {}

func (*vocabLang) GenerateRules(args language.GenerateArgs) language.GenerateResult {
	return language.GenerateResult{}
}

func (*vocabLang) Imports(c *config.Config, r *rule.Rule, f *rule.File) []resolve.ImportSpec {
	return nil
}

func (*vocabLang) Embeds(r *rule.Rule, from label.Label) []label.Label { return nil }

func (*vocabLang) Resolve(c *config.Config, ix *resolve.RuleIndex, rc *repo.RemoteCache, r *rule.Rule, imports interface{}, from label.Label) {
}
