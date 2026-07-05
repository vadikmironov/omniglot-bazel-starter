package lint_gazelle

// --- BEGIN lang:python ---
import (
	"github.com/bazelbuild/bazel-gazelle/language"
	"github.com/bazelbuild/bazel-gazelle/rule"
)

// pythonSourceKinds is the allowlist of source-rule kinds that get
// ruff and ty lint siblings. py_test is intentionally excluded — test
// sources would lint themselves recursively if included via
// srcs[:foo_test], and adding test linting later is a strict superset
// of this initial scope.
var pythonSourceKinds = map[string]bool{
	"py_binary":  true,
	"py_library": true,
}

// generateRuffTests emits a ruff_test sibling for each py_binary or
// py_library in the package, named "<src_name>.lint" with srcs
// pointing at the source rule and tagged "lint" so CI can pick it up
// via --test_tag_filters=lint.
func generateRuffTests(args language.GenerateArgs) []*rule.Rule {
	return generatePythonLintTests(args, kindRuffTest, ".lint")
}

// generateTyTests emits a ty_test sibling for each py_binary or
// py_library in the package, named "<src_name>.ty". ty is the Python
// type checker; the suffix differentiates it from the ruff_test
// sibling so they coexist in the same BUILD without collision.
func generateTyTests(args language.GenerateArgs) []*rule.Rule {
	return generatePythonLintTests(args, kindTyTest, ".ty")
}

// generatePythonLintTests is the shared body for the ruff and ty
// generators, mirroring generateJavaLintTests — the two-linter case is
// where per-language helpers benefit from sharing code.
func generatePythonLintTests(args language.GenerateArgs, kind, suffix string) []*rule.Rule {
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
		out = append(out, newLintRule(r.Name(), kind, suffix))
	}
	return out
}

// --- END lang:python ---
