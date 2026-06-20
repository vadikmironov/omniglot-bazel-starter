package lint_gazelle

// --- BEGIN lang:cpp ---
import (
	"github.com/bazelbuild/bazel-gazelle/language"
	"github.com/bazelbuild/bazel-gazelle/rule"
)

// cppSourceKinds is the allowlist of source-rule kinds that get a
// clang_tidy_test sibling. cc_test is intentionally excluded — adding
// test linting later is a strict superset of this initial scope. The
// clang_tidy aspect itself has no rule_kinds filter, so the safety
// gate is enforced here in the generator.
var cppSourceKinds = map[string]bool{
	"cc_binary":  true,
	"cc_library": true,
}

// generateClangTidyTests emits a clang_tidy_test sibling for each
// cc_binary or cc_library in the package, named "<src_name>.lint"
// with srcs pointing at the source rule and tagged "lint" so CI can
// pick it up via --test_tag_filters=lint.
func generateClangTidyTests(args language.GenerateArgs) []*rule.Rule {
	if args.File == nil {
		return nil
	}
	var out []*rule.Rule
	for _, r := range args.File.Rules {
		if !cppSourceKinds[r.Kind()] {
			continue
		}
		if hasSkipTag(r) {
			continue
		}
		out = append(out, newLintRule(r.Name(), kindClangTidyTest, ".lint"))
	}
	return out
}

// --- END lang:cpp ---
