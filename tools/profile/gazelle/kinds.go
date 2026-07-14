package profiling_gazelle

import "github.com/bazelbuild/bazel-gazelle/rule"

// Workload tags: the //tools/profile runner discovers targets by these,
// and the reaper uses them to recognise generated rules — the extension
// generates rules of general-purpose kinds (rust_binary), so ownership
// is established by the bench_/mem_ name prefix plus one of these tags,
// never by kind alone.
const (
	tagCPU = "profiling-cpu"
	tagMem = "profiling-mem"
)

const (
	// --- BEGIN lang:rust ---
	loadRustDefs   = "@rules_rust//rust:defs.bzl"
	kindRustBinary = "rust_binary"
	// --- END lang:rust ---
	// --- BEGIN lang:go ---
	loadGoDefs   = "@rules_go//go:def.bzl"
	kindGoBinary = "go_binary"
	kindGoTest   = "go_test"
	// --- END lang:go ---
	// --- BEGIN lang:cpp ---
	loadCcDefs   = "@rules_cc//cc:defs.bzl"
	kindCcBinary = "cc_binary"
	// --- END lang:cpp ---
	// --- BEGIN lang:python ---
	loadPyDefs   = "@rules_python//python:defs.bzl"
	kindPyBinary = "py_binary"
	kindPyTest   = "py_test"
	// --- END lang:python ---
	// --- BEGIN lang:java ---
	loadJavaDefs   = "@rules_java//java:defs.bzl"
	kindJavaBinary = "java_binary"
	// --- END lang:java ---
)

// profilingKinds declares the attributes gazelle may merge on generated
// workload rules. srcs/deps/crate_root/target_compatible_with track the
// generator's output on re-runs; tags stays mergeable so the discovery
// tag is enforced while user-added tags survive.
var profilingKinds = map[string]rule.KindInfo{
	// --- BEGIN lang:rust ---
	kindRustBinary: {
		NonEmptyAttrs: map[string]bool{"srcs": true},
		MergeableAttrs: map[string]bool{
			"srcs":                   true,
			"deps":                   true,
			"tags":                   true,
			"crate_root":             true,
			"target_compatible_with": true,
		},
	},
	// --- END lang:rust ---
	// --- BEGIN lang:go ---
	kindGoBinary: {
		NonEmptyAttrs: map[string]bool{"srcs": true},
		MergeableAttrs: map[string]bool{
			"srcs": true,
			"deps": true,
			"tags": true,
		},
	},
	kindGoTest: {
		NonEmptyAttrs: map[string]bool{"srcs": true},
		MergeableAttrs: map[string]bool{
			"srcs":  true,
			"embed": true,
			"tags":  true,
		},
	},
	// --- END lang:go ---
	// --- BEGIN lang:cpp ---
	kindCcBinary: {
		NonEmptyAttrs: map[string]bool{"srcs": true},
		MergeableAttrs: map[string]bool{
			"srcs": true,
			"deps": true,
			"tags": true,
		},
	},
	// --- END lang:cpp ---
	// --- BEGIN lang:python ---
	kindPyTest: {
		NonEmptyAttrs: map[string]bool{"srcs": true},
		MergeableAttrs: map[string]bool{
			"srcs": true,
			"deps": true,
			"tags": true,
			"args": true,
			"main": true,
			"size": true,
		},
	},
	kindPyBinary: {
		NonEmptyAttrs: map[string]bool{"srcs": true},
		MergeableAttrs: map[string]bool{
			"srcs":    true,
			"deps":    true,
			"tags":    true,
			"main":    true,
			"imports": true,
		},
	},
	// --- END lang:python ---
	// --- BEGIN lang:java ---
	kindJavaBinary: {
		NonEmptyAttrs: map[string]bool{"srcs": true},
		MergeableAttrs: map[string]bool{
			"srcs":       true,
			"deps":       true,
			"tags":       true,
			"main_class": true,
			"plugins":    true,
		},
	},
	// --- END lang:java ---
}

var profilingLoads = []rule.LoadInfo{
	// --- BEGIN lang:rust ---
	{
		Name:    loadRustDefs,
		Symbols: []string{kindRustBinary},
	},
	// --- END lang:rust ---
	// --- BEGIN lang:go ---
	{
		Name: loadGoDefs,
		Symbols: []string{
			kindGoBinary,
			kindGoTest,
		},
	},
	// --- END lang:go ---
	// --- BEGIN lang:cpp ---
	{
		Name:    loadCcDefs,
		Symbols: []string{kindCcBinary},
	},
	// --- END lang:cpp ---
	// --- BEGIN lang:python ---
	{
		Name: loadPyDefs,
		Symbols: []string{
			kindPyBinary,
			kindPyTest,
		},
	},
	// --- END lang:python ---
	// --- BEGIN lang:java ---
	{
		Name:    loadJavaDefs,
		Symbols: []string{kindJavaBinary},
	},
	// --- END lang:java ---
}
