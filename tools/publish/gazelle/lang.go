// Package publish_gazelle is a Gazelle language extension that
// auto-generates :publish and :publish_image targets for packages in
// this monorepo, driven by the convention "the rule whose name equals
// the package basename is the canonical publishable target."
//
// Scope is controlled by .publish.toml's [conventions].path_patterns
// allowlist: only packages whose relative path matches at least one
// pattern are considered. Within scope:
//
//   - Every canonical rule maps to a publish macro (binary_bundle_publish,
//     library_archive_publish, python_publish, java_publish,
//     java_binary_publish) and is emitted as :publish.
//   - Binary canonicals (cc_binary, go_binary, java_binary, py_binary,
//     rust_binary) additionally emit :publish_image (image_publish) when
//     [image_bases] in .publish.toml configures a base for that kind.
//
// Convention violations — no canonical found, canonical with non-publishable
// kind, [image_bases] missing for an in-scope binary kind — are reported as
// warnings; -publish_strict escalates them to errors.
//
// Opt-outs. Each *prunes* — it both suppresses generation and reaps any
// existing rule for the suppressed track on the next run (so adding the
// directive cleans up, not just freezes):
//
//   - # gazelle:publish_ignore — suppress + reap both rules.
//   - # gazelle:publish_ignore_artifact — suppress + reap :publish only.
//   - # gazelle:publish_ignore_image — suppress + reap :publish_image only.
//   - tags = ["no-publish"] on the canonical — suppress + reap both rules.
//
// The escape hatch from pruning is # gazelle:publish_ignore_keep, which freezes
// the package: no generation and no reaping, so hand-written / section-gated
// publish rules survive untouched.
//
// Sibling files: config.go (TOML loader + scope matcher + image config),
// kinds.go (publish-rule metadata used by gazelle's merger), generate.go
// (canonical inference + per-kind image formula + warning emission).
package publish_gazelle

import (
	"flag"
	"log"

	"github.com/bazelbuild/bazel-gazelle/config"
	"github.com/bazelbuild/bazel-gazelle/label"
	"github.com/bazelbuild/bazel-gazelle/language"
	"github.com/bazelbuild/bazel-gazelle/repo"
	"github.com/bazelbuild/bazel-gazelle/resolve"
	"github.com/bazelbuild/bazel-gazelle/rule"

	"omniglot-bazel-starter/tools/gazelle/directives"
)

const (
	extName = "publish"

	// directiveIgnore is the per-package opt-out. A BUILD file carrying
	// `# gazelle:publish_ignore` is excluded from inference and
	// enforcement entirely — neither :publish nor :publish_image is
	// emitted, regardless of path_patterns. The directive string is owned
	// by //tools/gazelle/directives so the vocab extension can advertise
	// it to sibling generators' binaries.
	directiveIgnore = directives.PublishIgnore

	// directiveIgnoreArtifact suppresses :publish only; :publish_image
	// is still emitted if the canonical's kind has a configured base.
	// Use when the artifact track (Maven/PyPI) doesn't apply but the
	// image track does (rare in practice).
	directiveIgnoreArtifact = directives.PublishIgnoreArtifact

	// directiveIgnoreImage suppresses :publish_image only; :publish is
	// emitted normally. Use to keep a binary in the artifact track but
	// out of the image track (e.g., a CLI tool that ships only as a
	// Maven artifact).
	directiveIgnoreImage = directives.PublishIgnoreImage

	// directiveKeep is the per-package freeze. A BUILD file carrying
	// `# gazelle:publish_ignore_keep` is left exactly as written: publish_gen
	// neither generates new publish rules nor reaps existing ones. Used to
	// hand-gate generated rules (e.g. wrapping them in feature:publish section
	// markers in a shipped BUILD file) without gazelle clobbering them. It is
	// the escape hatch from the pruning the ignore directives now perform.
	directiveKeep = directives.PublishIgnoreKeep

	// tagSkipPublish is the per-target opt-out. A canonical rule carrying
	// `tags = ["no-publish"]` is excluded from publish generation and any
	// existing :publish / :publish_image siblings are reaped — the rule-level
	// analogue of # gazelle:publish_ignore.
	tagSkipPublish = "no-publish"

	// flagStrict escalates convention warnings (no canonical found,
	// canonical with unpublishable kind, [image_bases] missing for an
	// in-scope binary kind) to hard errors. Intended for CI; default off
	// keeps local developer runs advisory.
	flagStrict = "publish_strict"

	// flagRemove is the global teardown switch. `-publish_remove` makes the
	// extension generate nothing and instead reap every existing publish
	// rule repo-wide (see GenerateRules / computeEmpty). The bootstrap tool
	// runs `bazel run //:publish_gen -- -publish_remove` to strip publish
	// targets from a target repo when the publish feature is dropped on
	// re-bootstrap, before tools/publish/ (its load targets) is pruned.
	flagRemove = "publish_remove"
)

// publishLang holds parsed conventions and per-run state shared between
// the Language-interface callbacks. gazelle instantiates this struct
// once per invocation and reuses it across every package walk; per-run
// maps (ignored) accumulate across Configure calls before GenerateRules
// consumes them.
type publishLang struct {
	conv       conventions
	imgCfg     imageConfig
	convLoaded bool

	// strict is bound to the -publish_strict flag in RegisterFlags.
	// Consulted by warn() in generate.go to decide log.Printf vs
	// log.Fatalf.
	strict bool

	// removeAll is bound to the -publish_remove flag. When set,
	// GenerateRules emits nothing and reaps every existing publish rule so
	// the whole feature can be torn down.
	removeAll bool

	// ignored tracks packages carrying # gazelle:publish_ignore
	// (suppresses both :publish and :publish_image).
	// ignoredArtifact / ignoredImage are the per-target variants — a
	// package may appear in zero, one, or both maps. GenerateRules
	// consults them independently when deciding which of the two rules
	// to emit. keep tracks packages frozen via # gazelle:publish_ignore_keep.
	ignored         map[string]bool
	ignoredArtifact map[string]bool
	ignoredImage    map[string]bool
	keep            map[string]bool
}

// NewLanguage is the entrypoint gazelle_binary calls to obtain an
// instance of this extension.
func NewLanguage() language.Language { return &publishLang{} }

func (*publishLang) Name() string { return extName }

func (*publishLang) Kinds() map[string]rule.KindInfo { return publishKinds }

func (*publishLang) Loads() []rule.LoadInfo { return publishLoads }

// GenerateRules is implemented in generate.go.

func (*publishLang) Fix(c *config.Config, f *rule.File) {}

// RegisterFlags binds extension-local flags to gazelle's shared FlagSet.
// The name is publish_-prefixed (not bare -strict) so enabling it doesn't
// escalate warnings from any other language extensions that may share
// this gazelle_binary in the future.
func (p *publishLang) RegisterFlags(fs *flag.FlagSet, cmd string, c *config.Config) {
	fs.BoolVar(&p.strict, flagStrict, false,
		"Treat publish_gazelle convention warnings as errors (fail-fast on first).")
	fs.BoolVar(&p.removeAll, flagRemove, false,
		"Remove all generated publish targets instead of generating them (used when the publish feature is dropped).")
}

func (*publishLang) CheckFlags(fs *flag.FlagSet, c *config.Config) error { return nil }

func (*publishLang) KnownDirectives() []string {
	return []string{directiveIgnore, directiveIgnoreArtifact, directiveIgnoreImage, directiveKeep}
}

// Configure is invoked once per package as gazelle walks the tree. It has
// two responsibilities: (1) load .publish.toml's [conventions] section
// on the first call (at the repo root, rel == "") — on parse error we
// log and continue with defaults so the extension remains usable on a
// freshly-templated repo; (2) record any # gazelle:publish_ignore
// directive so GenerateRules can short-circuit that package.
func (p *publishLang) Configure(c *config.Config, rel string, f *rule.File) {
	if !p.convLoaded {
		conv, img, err := loadConventions(c.RepoRoot)
		if err != nil {
			// On parse/validation error, fall back to a defaulted image
			// config rather than zero-value — otherwise emission would
			// write `app_prefix = ""` (binaries land at tar root, almost
			// never what the user wants).
			log.Printf("publish_gazelle: %v (continuing with defaults)", err)
			img = imageConfig{AppPrefix: defaultImageAppPrefix, Bases: map[string]string{}}
		}
		p.conv = conv
		p.imgCfg = img
		p.convLoaded = true
	}
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
		case directiveIgnoreArtifact:
			if p.ignoredArtifact == nil {
				p.ignoredArtifact = map[string]bool{}
			}
			p.ignoredArtifact[rel] = true
		case directiveIgnoreImage:
			if p.ignoredImage == nil {
				p.ignoredImage = map[string]bool{}
			}
			p.ignoredImage[rel] = true
		case directiveKeep:
			if p.keep == nil {
				p.keep = map[string]bool{}
			}
			p.keep[rel] = true
		}
	}
}

func (*publishLang) Imports(c *config.Config, r *rule.Rule, f *rule.File) []resolve.ImportSpec {
	return nil
}

func (*publishLang) Embeds(r *rule.Rule, from label.Label) []label.Label { return nil }

func (*publishLang) Resolve(c *config.Config, ix *resolve.RuleIndex, rc *repo.RemoteCache, r *rule.Rule, imports interface{}, from label.Label) {
}
