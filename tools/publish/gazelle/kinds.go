package publish_gazelle

import "github.com/bazelbuild/bazel-gazelle/rule"

// The publish rule kinds this extension owns, and the .bzl files
// that define them. Kept as constants because they're referenced from
// both Kinds()/Loads() (static tables) and GenerateRules() (inference).
const (
	loadGeneric = "//tools/publish/lang:generic_publish_defs.bzl"
	loadPython  = "//tools/publish/lang:python_publish_defs.bzl"
	loadJava    = "//tools/publish/lang:java_publish_defs.bzl"
	loadImage   = "//tools/publish/lang:image_publish_defs.bzl"

	kindBinaryBundle      = "binary_bundle_publish"
	kindLibraryArchive    = "library_archive_publish"
	kindPythonPublish     = "python_publish"
	kindJavaPublish       = "java_publish"
	kindJavaBinaryPublish = "java_binary_publish"
	kindImagePublish      = "image_publish"
)

// publishKinds declares the attributes gazelle is allowed to overwrite on
// each publish rule. Attributes outside MergeableAttrs are preserved as-is
// from the existing BUILD file — so users can add repo_name, visibility,
// classifier, etc. without fear of gazelle clobbering them on re-run.
//
// NonEmptyAttrs names the attribute whose absence marks a rule as empty so
// gazelle deletes it. Each is the rule's target attr (also Mergeable), so
// under -publish_remove the Empty merge strips it, the rule goes empty, and the
// whole rule — non-mergeable attrs (hdrs, base, …) included — is deleted. It is
// inert on normal runs, which never emit Empty rules.
var publishKinds = map[string]rule.KindInfo{
	kindBinaryBundle: {
		NonEmptyAttrs: map[string]bool{"binary_target": true},
		MergeableAttrs: map[string]bool{
			"artifact_id":   true,
			"binary_target": true,
		},
	},
	kindLibraryArchive: {
		// hdrs is intentionally NOT mergeable: it carries a glob(...) call
		// expression whose AST gazelle's merger can't compare, producing a
		// "could not merge expression" warning on every re-run. New pub
		// rules still receive hdrs on first emission (merge only kicks in
		// when an existing rule is present); on re-runs the user's value
		// is preserved untouched.
		NonEmptyAttrs: map[string]bool{"library_target": true},
		MergeableAttrs: map[string]bool{
			"artifact_id":    true,
			"library_target": true,
		},
	},
	kindPythonPublish: {
		NonEmptyAttrs: map[string]bool{"library_target": true},
		MergeableAttrs: map[string]bool{
			"distribution":   true,
			"library_target": true,
		},
	},
	kindJavaPublish: {
		NonEmptyAttrs: map[string]bool{"library_target": true},
		MergeableAttrs: map[string]bool{
			"artifact_id":    true,
			"library_target": true,
		},
	},
	kindJavaBinaryPublish: {
		NonEmptyAttrs: map[string]bool{"binary_target": true},
		MergeableAttrs: map[string]bool{
			"artifact_id":   true,
			"binary_target": true,
		},
	},
	// image_publish: per IMAGE_PUBLISH_SPEC.md "Auto-populated attributes"
	// table. `base` is intentionally NOT mergeable — it's resolved from
	// .publish.toml's [image_bases] and the spec calls for new emissions
	// only (don't rewrite a user's pinned base on .publish.toml change).
	// `runtime_args`, `cmd`, `extra_layers` are never auto-populated, so
	// they're absent from this map; user values are preserved by default.
	kindImagePublish: {
		NonEmptyAttrs: map[string]bool{"binary_target": true},
		MergeableAttrs: map[string]bool{
			"artifact_id":   true,
			"binary_target": true,
			"entrypoint":    true,
			"app_prefix":    true,
			"strip_prefix":  true,
		},
	},
}

// publishLoads tells gazelle which load() to emit for each kind it generates.
// The Symbols list per entry is authoritative — a kind must appear in exactly
// one LoadInfo.Symbols across the slice or gazelle's resolver panics.
var publishLoads = []rule.LoadInfo{
	{
		Name:    loadGeneric,
		Symbols: []string{kindBinaryBundle, kindLibraryArchive},
	},
	{
		Name:    loadPython,
		Symbols: []string{kindPythonPublish},
	},
	{
		Name:    loadJava,
		Symbols: []string{kindJavaPublish, kindJavaBinaryPublish},
	},
	{
		Name:    loadImage,
		Symbols: []string{kindImagePublish},
	},
}
