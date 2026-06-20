package publish_gazelle

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/BurntSushi/toml"
)

// Default values applied when the corresponding key is absent from
// .publish.toml or the file itself is missing. Keeps the extension
// usable on a freshly-templated repo with no conventions configured yet.
const (
	defaultPythonDistributionPrefix = ""

	// defaultImageAppPrefix mirrors image_publish_defs.bzl's app_prefix
	// default. Kept in lock-step so the gazelle-emitted attribute and
	// the macro default agree when the key is absent from .publish.toml.
	defaultImageAppPrefix = "app"
)

// conventions mirrors the [conventions] section of .publish.toml.
// Every field is optional; omitted keys fall back to the defaults above.
// Other sections (schemas, component_sets, components) are owned by the
// Python mint orchestrator and intentionally not parsed here.
type conventions struct {
	// PathPatterns is an allowlist of repo-relative paths where gazelle
	// should emit :publish targets. A package is in scope iff its relative
	// path matches at least one pattern. An empty/missing list means
	// "every package is in scope" (pre-config behaviour).
	//
	// Supported syntax per pattern:
	//   "foo/bar"   — exact match
	//   "foo/*"     — immediate children of foo/
	//   "foo/**"    — foo/ and any descendant (common case)
	PathPatterns []string `toml:"path_patterns"`

	// PythonDistributionPrefix is prepended (with a "-" separator) to the
	// kebab-cased package basename to form the final wheel distribution
	// name. For prefix "omniglot-bazel-starter" and package "python_lib", the
	// distribution becomes "omniglot-bazel-starter-python-lib". If empty, the
	// distribution equals the kebab-cased basename with no prefix.
	PythonDistributionPrefix string `toml:"python_distribution_prefix"`

	// ImageAppPrefix is the in-image filesystem prefix passed through to
	// each emitted image_publish rule's app_prefix attribute. Empty string
	// is allowed (binary lands at tar root); leading/trailing slashes and
	// ".." segments are rejected. Defaults to "app" when omitted, matching
	// the image_publish macro default.
	ImageAppPrefix *string `toml:"image_app_prefix"`
}

// publishConfig holds the minimum subset of .publish.toml this extension cares
// about. Having a named outer struct (rather than decoding straight into
// conventions) lets us add future top-level sections without reshuffling the
// loader signature.
type publishConfig struct {
	Conventions conventions       `toml:"conventions"`
	ImageBases  map[string]string `toml:"image_bases"`
}

// imageConfig is the resolved image-publishing config exposed to GenerateRules.
// Built once by loadConventions from the [conventions] and [image_bases]
// sections of .publish.toml; never mutated thereafter.
type imageConfig struct {
	// AppPrefix is the validated in-image filesystem prefix. May be
	// empty; never has leading/trailing slash or ".." segments.
	AppPrefix string

	// Bases maps canonical binary kind ("java_binary", "py_binary", …)
	// to the base image label gazelle should emit. A kind absent from
	// this map means "no [image_bases] entry configured", which causes
	// generate.go to warn and skip :publish_image emission for that kind
	// (the artifact :publish target is unaffected).
	Bases map[string]string
}

// loadConventions reads repoRoot/.publish.toml and returns the [conventions]
// block plus the derived [image_bases] map. Missing file → zero-value
// conventions and an empty image config (extension still runs, just with
// defaults; image emission no-ops because Bases is empty). Malformed TOML
// → error (caller logs and falls back). Validation errors on the resolved
// image_app_prefix are returned the same way; the file is treated as
// unrecoverable, not silently downgraded, because an invalid prefix would
// produce broken image_publish calls.
func loadConventions(repoRoot string) (conventions, imageConfig, error) {
	path := filepath.Join(repoRoot, ".publish.toml")
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return conventions{}, imageConfig{AppPrefix: defaultImageAppPrefix}, nil
		}
		return conventions{}, imageConfig{}, fmt.Errorf("read %s: %w", path, err)
	}
	var cfg publishConfig
	if _, err := toml.Decode(string(data), &cfg); err != nil {
		return conventions{}, imageConfig{}, fmt.Errorf("parse %s: %w", path, err)
	}
	img, err := resolveImageConfig(cfg)
	if err != nil {
		return conventions{}, imageConfig{}, fmt.Errorf("%s: %w", path, err)
	}
	return cfg.Conventions, img, nil
}

// resolveImageConfig applies defaults and validation to the raw TOML and
// produces the imageConfig consumed by generate.go. Validation rules
// (per IMAGE_PUBLISH_SPEC.md): empty AppPrefix is OK; leading/trailing
// slash is fatal; ".." segments are fatal. [image_bases] is taken
// verbatim — missing entries are surfaced at GenerateRules time as a
// per-kind warning, not here, because we don't yet know which kinds are
// in scope.
func resolveImageConfig(cfg publishConfig) (imageConfig, error) {
	prefix := defaultImageAppPrefix
	if cfg.Conventions.ImageAppPrefix != nil {
		prefix = *cfg.Conventions.ImageAppPrefix
	}
	if err := validateImageAppPrefix(prefix); err != nil {
		return imageConfig{}, err
	}
	bases := cfg.ImageBases
	if bases == nil {
		bases = map[string]string{}
	}
	return imageConfig{AppPrefix: prefix, Bases: bases}, nil
}

// validateImageAppPrefix mirrors the macro's _validate_app_prefix in
// image_publish_defs.bzl. Rejecting these patterns at gazelle time gives
// users a config-level error message rather than a deferred macro fail()
// at the next bazel build.
func validateImageAppPrefix(prefix string) error {
	if strings.HasPrefix(prefix, "/") {
		return fmt.Errorf("[conventions].image_app_prefix must not have a leading slash; got %q", prefix)
	}
	if strings.HasSuffix(prefix, "/") {
		return fmt.Errorf("[conventions].image_app_prefix must not have a trailing slash; got %q", prefix)
	}
	for _, seg := range strings.Split(prefix, "/") {
		if seg == ".." {
			return fmt.Errorf("[conventions].image_app_prefix must not contain '..' segments; got %q", prefix)
		}
	}
	return nil
}

// inScope reports whether the given repo-relative package path should be
// considered for :publish generation. An empty PathPatterns list short-
// circuits to true so unconfigured repos keep working. Any non-empty list
// requires at least one pattern to match — this is how tools/bootstrap
// and other non-publishable packages stay out of scope.
func (c conventions) inScope(rel string) bool {
	if len(c.PathPatterns) == 0 {
		return true
	}
	for _, p := range c.PathPatterns {
		if matchPathPattern(p, rel) {
			return true
		}
	}
	return false
}

// matchPathPattern is a minimal glob matcher tailored to the three patterns
// we actually use in repos: exact, single-segment wildcard, recursive
// wildcard. Not a full doublestar implementation — but it's enough for
// .publish.toml and avoids pulling in a glob library.
func matchPathPattern(pattern, rel string) bool {
	if pattern == rel {
		return true
	}
	if strings.HasSuffix(pattern, "/**") {
		prefix := strings.TrimSuffix(pattern, "/**")
		return rel == prefix || strings.HasPrefix(rel, prefix+"/")
	}
	if strings.HasSuffix(pattern, "/*") {
		prefix := strings.TrimSuffix(pattern, "/*")
		if !strings.HasPrefix(rel, prefix+"/") {
			return false
		}
		return !strings.Contains(rel[len(prefix)+1:], "/")
	}
	return false
}
