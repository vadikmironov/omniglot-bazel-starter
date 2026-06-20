package lint_gazelle

// --- BEGIN lang:java ---
import (
	"github.com/bazelbuild/bazel-gazelle/language"
	"github.com/bazelbuild/bazel-gazelle/rule"
)

// javaSourceKinds is the allowlist of source-rule kinds that get pmd
// and spotbugs lint siblings. java_test is intentionally excluded —
// adding test linting later is a strict superset of this initial
// scope.
var javaSourceKinds = map[string]bool{
	"java_binary":  true,
	"java_library": true,
}

// generatePmdTests emits a pmd_test sibling for each java_binary or
// java_library in the package, named "<src_name>.pmd_lint".
func generatePmdTests(args language.GenerateArgs) []*rule.Rule {
	return generateJavaLintTests(args, kindPmdTest, ".pmd_lint")
}

// generateSpotbugsTests emits a spotbugs_test sibling for each
// java_binary or java_library in the package, named
// "<src_name>.spotbugs_lint". Java is the only language with two
// linters per source rule; the suffix differentiates the test names
// so they coexist in the same BUILD without collision.
func generateSpotbugsTests(args language.GenerateArgs) []*rule.Rule {
	return generateJavaLintTests(args, kindSpotbugsTest, ".spotbugs_lint")
}

// generateJavaLintTests is the shared body for pmd and spotbugs
// generators — Java's two-linter case is the only place per-language
// helpers benefit from sharing code.
func generateJavaLintTests(args language.GenerateArgs, kind, suffix string) []*rule.Rule {
	if args.File == nil {
		return nil
	}
	var out []*rule.Rule
	for _, r := range args.File.Rules {
		if !javaSourceKinds[r.Kind()] {
			continue
		}
		if hasSkipTag(r) {
			continue
		}
		out = append(out, newLintRule(r.Name(), kind, suffix))
	}
	return out
}

// --- END lang:java ---
