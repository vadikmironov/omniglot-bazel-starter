package lint_gazelle

import "github.com/bazelbuild/bazel-gazelle/rule"

// The lint_test kinds this extension owns, and the .bzl file that
// defines them. //tools/lint:linters.bzl is the single source of
// truth for lint_test factories; each language segment here enables
// one or more symbols from that file.
const (
	loadLinters = "//tools/lint:linters.bzl"

	// --- BEGIN lang:cpp ---
	kindClangTidyTest = "clang_tidy_test"
	// --- END lang:cpp ---
	// --- BEGIN lang:rust ---
	kindClippyTest = "clippy_test"
	// --- END lang:rust ---
	// --- BEGIN lang:java ---
	kindPmdTest      = "pmd_test"
	kindSpotbugsTest = "spotbugs_test"
	// --- END lang:java ---
	// --- BEGIN lang:python ---
	kindRuffTest = "ruff_test"
	// --- END lang:python ---
)

// lintKinds declares the attributes gazelle is allowed to overwrite on
// each lint_test rule. srcs is mergeable so re-runs can update the
// canonical-target label; tags is NOT mergeable so users who add
// custom tags (e.g. "requires-network") retain them across re-runs.
var lintKinds = map[string]rule.KindInfo{
	// --- BEGIN lang:cpp ---
	kindClangTidyTest: {
		MatchAttrs:     []string{"srcs"},
		NonEmptyAttrs:  map[string]bool{"srcs": true},
		MergeableAttrs: map[string]bool{"srcs": true, "tags": true},
	},
	// --- END lang:cpp ---
	// --- BEGIN lang:rust ---
	kindClippyTest: {
		MatchAttrs:     []string{"srcs"},
		NonEmptyAttrs:  map[string]bool{"srcs": true},
		MergeableAttrs: map[string]bool{"srcs": true, "tags": true},
	},
	// --- END lang:rust ---
	// --- BEGIN lang:java ---
	kindPmdTest: {
		MatchAttrs:     []string{"srcs"},
		NonEmptyAttrs:  map[string]bool{"srcs": true},
		MergeableAttrs: map[string]bool{"srcs": true, "tags": true},
	},
	kindSpotbugsTest: {
		MatchAttrs:     []string{"srcs"},
		NonEmptyAttrs:  map[string]bool{"srcs": true},
		MergeableAttrs: map[string]bool{"srcs": true, "tags": true},
	},
	// --- END lang:java ---
	// --- BEGIN lang:python ---
	kindRuffTest: {
		MatchAttrs:     []string{"srcs"},
		NonEmptyAttrs:  map[string]bool{"srcs": true},
		MergeableAttrs: map[string]bool{"srcs": true, "tags": true},
	},
	// --- END lang:python ---
}

// lintLoads tells gazelle which load() to emit for each kind it
// generates. All lint_test factories live in a single linters.bzl,
// so the Symbols list is flat with per-language markers — a
// scaffolded fork that omits (say) cpp strips "clang_tidy_test"
// from the Symbols slice. A zero-symbol slice causes gazelle to
// skip the load entirely, matching the "no rules emitted" state.
var lintLoads = []rule.LoadInfo{
	{
		Name: loadLinters,
		Symbols: []string{
			// --- BEGIN lang:cpp ---
			kindClangTidyTest,
			// --- END lang:cpp ---
			// --- BEGIN lang:rust ---
			kindClippyTest,
			// --- END lang:rust ---
			// --- BEGIN lang:java ---
			kindPmdTest,
			kindSpotbugsTest,
			// --- END lang:java ---
			// --- BEGIN lang:python ---
			kindRuffTest,
			// --- END lang:python ---
		},
	},
}
