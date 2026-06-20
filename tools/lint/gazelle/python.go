package lint_gazelle

// --- BEGIN lang:python ---
import (
	"github.com/bazelbuild/bazel-gazelle/language"
	"github.com/bazelbuild/bazel-gazelle/rule"
)

// pythonSourceKinds is the allowlist of source-rule kinds that get a
// ruff_test sibling. py_test is intentionally excluded — test sources
// would lint themselves recursively if included via srcs[:foo_test],
// and adding test linting later is a strict superset of this initial
// scope.
var pythonSourceKinds = map[string]bool{
	"py_binary":  true,
	"py_library": true,
}

// generateRuffTests emits a ruff_test sibling for each py_binary or
// py_library in the package, named "<src_name>.lint" with srcs
// pointing at the source rule and tagged "lint" so CI can pick it up
// via --test_tag_filters=lint.
func generateRuffTests(args language.GenerateArgs) []*rule.Rule {
	if args.File == nil {
		return nil
	}
	var out []*rule.Rule
	for _, r := range args.File.Rules {
		if !pythonSourceKinds[r.Kind()] {
			continue
		}
		if hasSkipTag(r) {
			continue
		}
		out = append(out, newLintRule(r.Name(), kindRuffTest, ".lint"))
	}
	return out
}

// --- END lang:python ---
