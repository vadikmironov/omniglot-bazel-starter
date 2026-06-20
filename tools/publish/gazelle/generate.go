package publish_gazelle

import (
	"fmt"
	"log"
	"path"
	"strings"

	"github.com/bazelbuild/bazel-gazelle/language"
	"github.com/bazelbuild/bazel-gazelle/rule"
)

// publishBinding pairs a canonical rule kind (cc_binary, py_library, …)
// with the publish kind it maps to. role distinguishes "binary" from
// "library" since those affect which target attribute we emit
// (binary_target vs library_target).
type publishBinding struct {
	publishKind string
	role        string
}

// pythonDistribution composes the wheel distribution name from a
// configured prefix and a kebab-cased artifact id. An empty prefix
// yields just the artifact id (no leading dash).
func pythonDistribution(prefix, artifactID string) string {
	if prefix == "" {
		return artifactID
	}
	return prefix + "-" + artifactID
}

const (
	roleBinary  = "binary"
	roleLibrary = "library"

	// tagPublishBundle, when present in a java_binary's `tags` attribute,
	// downgrades its publish target from java_binary_publish (fat JAR, the
	// JVM-idiomatic default) back to binary_bundle_publish (a zip of the
	// launcher script plus its classpath JAR fan-out, matching how
	// cc_binary/go_binary/etc. publish). Useful when the binary's runfiles
	// include sibling files that callers expect to receive alongside it.
	tagPublishBundle = "publish_bundle"
)

// canonicalBindings is the one-to-one mapping from canonical source-rule kind
// to publish-rule kind. Ten entries covering all binaries + libraries the
// repo ships. Language-specific libraries (java_library, py_library) route
// to their own publish macros; everything else uses the generic pair.
var canonicalBindings = map[string]publishBinding{
	"cc_binary":    {kindBinaryBundle, roleBinary},
	"cc_library":   {kindLibraryArchive, roleLibrary},
	"go_binary":    {kindBinaryBundle, roleBinary},
	"go_library":   {kindLibraryArchive, roleLibrary},
	"java_binary":  {kindJavaBinaryPublish, roleBinary},
	"java_library": {kindJavaPublish, roleLibrary},
	"py_binary":    {kindBinaryBundle, roleBinary},
	"py_library":   {kindPythonPublish, roleLibrary},
	"rust_binary":  {kindBinaryBundle, roleBinary},
	"rust_library": {kindLibraryArchive, roleLibrary},
}

// imageFormula carries the per-kind image_publish attribute templates,
// each derived purely from the canonical rule name and package path.
// Centralising these in a table (rather than inline switches) keeps the
// per-kind reasoning side-by-side and unit-testable in isolation.
type imageFormula struct {
	// binaryTargetSuffix is appended to the canonical's label to form the
	// binary_target attribute. Empty for native binaries; "_deploy.jar"
	// for java_binary, which packages the canonical's fat JAR.
	binaryTargetSuffix string

	// stripPrefix returns the value emitted as image_publish.strip_prefix
	// given the package's repo-relative path and the canonical rule name.
	// tar.bzl preserves workspace-relative paths by default, so we strip
	// the package_name() (and, for go/rust, the rules-go/rust internal
	// "<name>_/" subdirectory) to land the binary at /<app_prefix>/<name>.
	stripPrefix func(pkgPath, name string) string

	// entrypoint returns the entrypoint list with one occurrence of the
	// in-image binary path substituted in. {runtime_args} placeholders
	// are emitted as-is — runtime_args itself is never auto-populated,
	// but the placeholder is left in place so users adding runtime_args
	// later (e.g., JVM heap flags) don't have to also rewrite entrypoint.
	entrypoint func(appPrefix, name string) []string
}

// imageFormulas is the per-kind table referenced from
// IMAGE_PUBLISH_SPEC.md. Library kinds are intentionally absent — only
// binary canonicals receive :publish_image. New binary kinds added to
// canonicalBindings must also be added here, otherwise generate.go skips
// image emission silently for them (which would be a real bug).
var imageFormulas = map[string]imageFormula{
	"java_binary": {
		binaryTargetSuffix: "_deploy.jar",
		stripPrefix:        func(pkgPath, _ string) string { return pkgPath },
		entrypoint: func(appPrefix, name string) []string {
			return []string{"java", "{runtime_args}", "-jar", inImagePath(appPrefix, name+"_deploy.jar")}
		},
	},
	"go_binary": {
		stripPrefix: func(pkgPath, name string) string { return pkgPath + "/" + name + "_" },
		entrypoint:  func(appPrefix, name string) []string { return []string{inImagePath(appPrefix, name)} },
	},
	"rust_binary": {
		stripPrefix: func(pkgPath, name string) string { return pkgPath + "/" + name + "_" },
		entrypoint:  func(appPrefix, name string) []string { return []string{inImagePath(appPrefix, name)} },
	},
	"cc_binary": {
		stripPrefix: func(pkgPath, _ string) string { return pkgPath },
		entrypoint:  func(appPrefix, name string) []string { return []string{inImagePath(appPrefix, name)} },
	},
	"py_binary": {
		stripPrefix: func(pkgPath, _ string) string { return pkgPath },
		entrypoint:  func(appPrefix, name string) []string { return []string{inImagePath(appPrefix, name)} },
	},
}

// inImagePath joins app_prefix and a single binary basename into the
// in-image absolute path. Empty app_prefix lays the binary at "/<name>"
// (tar root); non-empty produces "/<app_prefix>/<name>".
func inImagePath(appPrefix, basename string) string {
	if appPrefix == "" {
		return "/" + basename
	}
	return "/" + appPrefix + "/" + basename
}

// GenerateRules emits up to two rules per eligible package: a :publish
// rule (always, for every publishable canonical kind) and, for binary
// canonicals only, a :publish_image rule when [image_bases] supplies a
// base for that kind. Eligibility checks (in order):
//
//	(a) package is not frozen via # gazelle:publish_ignore_keep;
//	(b) path is in scope per .publish.toml's [conventions].path_patterns;
//	(c) package is not blanket-opted-out via # gazelle:publish_ignore;
//	(d) BUILD contains a rule whose name equals the package basename
//	    (canonical) whose kind appears in canonicalBindings, not tagged
//	    "no-publish".
//
// :publish is additionally suppressed by # gazelle:publish_ignore_artifact;
// :publish_image is suppressed by # gazelle:publish_ignore_image, by the
// canonical not being a binary kind, or by [image_bases] missing an entry
// for that kind.
//
// Reaping (Empty) is driven by *explicit* opt-out only — publish_ignore,
// publish_ignore_artifact/_image, the no-publish tag, and -publish_remove all
// reap the rule(s) of the track they suppress, so adding the opt-out cleans up
// the orphan. A missing [image_bases] entry or a renamed/absent canonical is a
// warning, not an opt-out: those deliberately leave existing rules alone, so a
// transient config gap never silently deletes a working rule. publish_ignore_keep
// and out-of-scope reap nothing.
func (p *publishLang) GenerateRules(args language.GenerateArgs) language.GenerateResult {
	// Freeze first — publish_ignore_keep shields the package from generation,
	// reaping, and -publish_remove alike, so hand-gated rules survive.
	if p.keep[args.Rel] {
		return language.GenerateResult{}
	}
	// -publish_remove: reap every publish rule repo-wide, ignoring scope and
	// opt-outs. The whole-feature teardown the bootstrap tool runs on drop.
	if p.removeAll {
		return language.GenerateResult{Empty: ownedRules(args, nil)}
	}
	if args.File == nil || args.Rel == "" {
		return language.GenerateResult{}
	}
	// Out of scope: publish_gen neither generates nor reaps here.
	if !p.conv.inScope(args.Rel) {
		return language.GenerateResult{}
	}
	// publish_ignore: suppress and reap both tracks for this package.
	if p.ignored[args.Rel] {
		return language.GenerateResult{Empty: ownedRules(args, nil)}
	}

	baseName := path.Base(args.Rel)

	// Two-stage lookup so we can distinguish (i) "no rule matches basename"
	// from (ii) "rule matches but its kind isn't publishable". Each case
	// warrants a different convention-violation message. Both are warnings,
	// not opt-outs, so neither reaps (a rename shouldn't delete the orphan
	// out from under a half-finished refactor).
	var nameMatch *rule.Rule
	for _, r := range args.File.Rules {
		if r.Name() == baseName {
			nameMatch = r
			break
		}
	}
	if nameMatch == nil {
		p.warn(args.Rel, "no canonical rule found: expected a rule named %q. "+
			"Rename the publishable rule to match the package basename, or add "+
			"# gazelle:%s to suppress.", baseName, directiveIgnore)
		return language.GenerateResult{}
	}
	binding, ok := canonicalBindings[nameMatch.Kind()]
	if !ok {
		p.warn(args.Rel, "canonical rule %q has kind %q which is not publishable. "+
			"Change the rule kind, or add # gazelle:%s to suppress.",
			baseName, nameMatch.Kind(), directiveIgnore)
		return language.GenerateResult{}
	}
	canonical := nameMatch

	// no-publish tag: the canonical opts itself out of both tracks. Reap both —
	// the rule-level analogue of publish_ignore.
	if hasTag(canonical, tagSkipPublish) {
		return language.GenerateResult{Empty: ownedRules(args, nil)}
	}

	// Per-rule opt-out: a java_binary tagged "publish_bundle" reverts to the
	// generic binary_bundle_publish path. The default for java_binary is
	// the fat-JAR java_binary_publish, but some apps need their runfiles
	// fanned out alongside the JAR (e.g., bundled config files, native
	// libraries) — those keep the polyglot zip-bundle behaviour.
	if canonical.Kind() == "java_binary" && hasTag(canonical, tagPublishBundle) {
		binding = publishBinding{kindBinaryBundle, roleBinary}
	}

	var gen, empty []*rule.Rule
	// Artifact track: generate, or (when opted out) reap the existing rule.
	if p.ignoredArtifact[args.Rel] {
		empty = append(empty, ownedRules(args, isArtifactKind)...)
	} else {
		gen = append(gen, p.buildArtifactRule(canonical, binding, baseName))
	}
	// Image track (binaries only).
	if binding.role == roleBinary {
		if p.ignoredImage[args.Rel] {
			empty = append(empty, ownedRules(args, isImageKind)...)
		} else if img := p.buildImageRule(canonical, args.Rel, baseName); img != nil {
			gen = append(gen, img)
		}
		// img == nil means buildImageRule warned about a missing [image_bases]
		// entry — a config gap, not an opt-out, so we deliberately do not reap
		// an existing :publish_image here.
	}
	imports := make([]interface{}, len(gen))
	return language.GenerateResult{Gen: gen, Imports: imports, Empty: empty}
}

// ownedRules returns a placeholder rule for every existing rule of a kind this
// extension owns (optionally narrowed by pred), so gazelle deletes each on the
// next run. A nil pred matches every owned kind. Deletion relies on each
// publish kind's KindInfo.NonEmptyAttrs (see kinds.go) — without it gazelle
// would only strip the mergeable attrs and leave a hollow rule behind.
func ownedRules(args language.GenerateArgs, pred func(kind string) bool) []*rule.Rule {
	if args.File == nil {
		return nil
	}
	var empty []*rule.Rule
	for _, r := range args.File.Rules {
		if _, owned := publishKinds[r.Kind()]; !owned {
			continue
		}
		if pred != nil && !pred(r.Kind()) {
			continue
		}
		empty = append(empty, rule.NewRule(r.Kind(), r.Name()))
	}
	return empty
}

// isImageKind / isArtifactKind partition the owned publish kinds into the two
// tracks, so publish_ignore_image and publish_ignore_artifact reap only their
// own track's rules.
func isImageKind(kind string) bool    { return kind == kindImagePublish }
func isArtifactKind(kind string) bool { return kind != kindImagePublish }

// buildArtifactRule emits the :publish rule. Pure of any image concerns
// — splitting it out keeps the historical artifact-only path unchanged.
func (p *publishLang) buildArtifactRule(canonical *rule.Rule, binding publishBinding, baseName string) *rule.Rule {
	pub := rule.NewRule(binding.publishKind, "publish")
	artifactID := strings.ReplaceAll(baseName, "_", "-")
	targetLabel := ":" + canonical.Name()

	switch binding.publishKind {
	case kindBinaryBundle, kindJavaBinaryPublish:
		pub.SetAttr("artifact_id", artifactID)
		pub.SetAttr("binary_target", targetLabel)
	case kindLibraryArchive:
		pub.SetAttr("artifact_id", artifactID)
		// Replicate hdrs expression (e.g. glob(...)) from the canonical
		// cc_library so header fan-out in the published archive matches
		// what the library itself exposes. Absent on rust/go libraries.
		if hdrs := canonical.Attr("hdrs"); hdrs != nil {
			pub.SetAttr("hdrs", hdrs)
		}
		pub.SetAttr("library_target", targetLabel)
	case kindPythonPublish:
		pub.SetAttr("distribution", pythonDistribution(p.conv.PythonDistributionPrefix, artifactID))
		pub.SetAttr("library_target", targetLabel)
	case kindJavaPublish:
		pub.SetAttr("artifact_id", artifactID)
		pub.SetAttr("library_target", targetLabel)
	}
	return pub
}

// buildImageRule emits the :publish_image rule for a binary canonical.
// Returns nil when [image_bases] has no entry for the canonical's kind
// (warn-by-default; fatal under -publish_strict). Per-kind formulas live
// in imageFormulas — this function is purely the orchestration around
// them: name, base lookup, attribute fill-in.
//
// The publish_bundle override (java_binary tag → binary_bundle_publish on
// the artifact track) is intentionally NOT applied here. publish_bundle
// concerns archive shape, not container shape; both java image variants
// (fat JAR vs. polyglot bundle) still want a Java image, so the formula
// is keyed on the canonical's actual kind, not its routed publish kind.
func (p *publishLang) buildImageRule(canonical *rule.Rule, rel, baseName string) *rule.Rule {
	formula, ok := imageFormulas[canonical.Kind()]
	if !ok {
		// canonicalBindings says it's a binary, imageFormulas doesn't
		// have it — that's a code-level oversight, not a user issue.
		// Surface it as a warning so it gets noticed without breaking
		// the run (canonicalBindings still emitted the artifact rule).
		p.warn(rel, "kind %q is a binary in canonicalBindings but has no image formula; "+
			"add it to imageFormulas in generate.go.", canonical.Kind())
		return nil
	}
	base, hasBase := p.imgCfg.Bases[canonical.Kind()]
	if !hasBase {
		p.warn(rel, "no [image_bases] entry for kind %q; skipping :publish_image. "+
			"Add `%s = \"@<base>\"` under [image_bases] in .publish.toml, "+
			"or add # gazelle:%s to suppress this warning for this package.",
			canonical.Kind(), canonical.Kind(), directiveIgnoreImage)
		return nil
	}

	artifactID := strings.ReplaceAll(baseName, "_", "-")
	targetLabel := ":" + canonical.Name() + formula.binaryTargetSuffix
	stripPrefix := formula.stripPrefix(rel, canonical.Name())
	entrypoint := formula.entrypoint(p.imgCfg.AppPrefix, canonical.Name())

	img := rule.NewRule(kindImagePublish, "publish_image")
	img.SetAttr("artifact_id", artifactID)
	img.SetAttr("base", base)
	img.SetAttr("binary_target", targetLabel)
	img.SetAttr("entrypoint", entrypoint)
	img.SetAttr("app_prefix", p.imgCfg.AppPrefix)
	img.SetAttr("strip_prefix", stripPrefix)
	return img
}

// hasTag reports whether the rule's `tags` list literal contains the given
// string. Returns false when tags is absent or set to an expression gazelle
// can't decompose into static strings (e.g. a select() — none of our
// canonical rules use that).
func hasTag(r *rule.Rule, tag string) bool {
	for _, t := range r.AttrStrings("tags") {
		if t == tag {
			return true
		}
	}
	return false
}

// warn reports a convention violation for the given package. In default
// mode it's a log line; in strict mode it's a fail-fast: the extension
// has no post-walk hook to batch warnings, so any warning in strict mode
// aborts the run immediately with a non-zero exit code.
func (p *publishLang) warn(rel, format string, args ...interface{}) {
	msg := fmt.Sprintf("publish_gazelle [%s]: "+format, append([]interface{}{rel}, args...)...)
	if p.strict {
		log.Fatal(msg)
	}
	log.Println(msg)
}
