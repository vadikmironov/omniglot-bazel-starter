package lint_gazelle

// --- BEGIN lang:rust ---
import (
	"github.com/bazelbuild/bazel-gazelle/language"
	"github.com/bazelbuild/bazel-gazelle/rule"
)

// rustSourceKinds is the allowlist of source-rule kinds that get a
// clippy_test sibling. It must stay a subset of the clippy aspect's
// rule_kinds in //tools/lint:linters.bzl (which currently takes the
// upstream default): emitting clippy_test against a kind the aspect
// excludes fails analysis with "OutputGroupInfo value has no field
// rules_lint_human" because the aspect returns only the internal output
// group on excluded kinds.
var rustSourceKinds = map[string]bool{
	"rust_binary":         true,
	"rust_library":        true,
	"rust_shared_library": true,
	"rust_test":           true,
}

// generateClippyTests emits a clippy_test sibling for each rust source
// rule in the package, named "<src_name>.lint" with srcs
// pointing at the source rule and tagged "lint" so CI can pick it up
// via --test_tag_filters=lint.
func generateClippyTests(args language.GenerateArgs) []*rule.Rule {
	if args.File == nil {
		return nil
	}
	var out []*rule.Rule
	for _, r := range args.File.Rules {
		if !rustSourceKinds[r.Kind()] {
			continue
		}
		if hasSkipTag(r) {
			continue
		}
		out = append(out, newLintRule(r.Name(), kindClippyTest, ".lint"))
	}
	return out
}

// --- END lang:rust ---
