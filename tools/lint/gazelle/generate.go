package lint_gazelle

import (
	"github.com/bazelbuild/bazel-gazelle/language"
	"github.com/bazelbuild/bazel-gazelle/rule"
)

// GenerateRules dispatches to per-language generators based on which
// language segments are present in this scaffold. Each per-language
// hook inspects args.File.Rules for source rules whose kind matches
// that linter's allowlist; per-target opt-out via tags = ["no-lint"]
// is honoured by every generator (see hasSkipTag in lang.go).
// Per-package opt-out via the # gazelle:lint_ignore directive is
// honoured here, suppressing generation entirely for that package.
//
// Per-package freeze via the # gazelle:lint_ignore_keep directive is
// honoured first: such packages return an empty result with no Gen and
// no Empty, so gazelle neither adds nor removes lint_test rules and the
// hand-written (e.g. section-gated) rules are left untouched.
//
// After dispatch, any pre-existing rule of an owned kind that is not
// in the generated set is added to Empty so gazelle deletes it. This
// is what gives lint_ignore and no-lint their "remove on next run"
// behaviour: returning Gen with fewer rules is not enough — gazelle
// preserves owned rules unless explicitly told to delete them.
//
// Under -lint_remove (p.removeAll) generation is suppressed in every
// package, so computeEmpty reaps all owned rules repo-wide — the whole-
// feature teardown the bootstrap tool runs when lint is dropped. Frozen
// (lint_ignore_keep) packages are still left untouched, since their
// hand-gated rules ship via section markers, not gazelle.
func (p *lintLang) GenerateRules(args language.GenerateArgs) language.GenerateResult {
	if p.keep[args.Rel] {
		return language.GenerateResult{}
	}

	var rules []*rule.Rule
	if !p.removeAll && !p.ignored[args.Rel] {
		// --- BEGIN lang:cpp ---
		rules = append(rules, generateClangTidyTests(args)...)
		// --- END lang:cpp ---
		// --- BEGIN lang:rust ---
		rules = append(rules, generateClippyTests(args)...)
		// --- END lang:rust ---
		// --- BEGIN lang:java ---
		rules = append(rules, generatePmdTests(args)...)
		rules = append(rules, generateSpotbugsTests(args)...)
		// --- END lang:java ---
		// --- BEGIN lang:python ---
		rules = append(rules, generateRuffTests(args)...)
		// --- END lang:python ---
	}

	imports := make([]interface{}, len(rules))
	return language.GenerateResult{
		Gen:     rules,
		Imports: imports,
		Empty:   computeEmpty(args, rules),
	}
}

// computeEmpty walks the existing BUILD for rules of kinds we own and
// returns those whose names are not in the regenerated set. Gazelle
// deletes each returned placeholder rule on the next run. Used to
// reap orphans from lint_ignore, no-lint, source-rule renames, and
// source-rule deletions.
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
		if _, owned := lintKinds[r.Kind()]; !owned {
			continue
		}
		if keep[r.Name()] {
			continue
		}
		empty = append(empty, rule.NewRule(r.Kind(), r.Name()))
	}
	return empty
}
