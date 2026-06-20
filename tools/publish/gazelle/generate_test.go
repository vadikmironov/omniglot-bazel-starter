package publish_gazelle

import (
	"path"
	"path/filepath"
	"reflect"
	"sort"
	"testing"

	"github.com/bazelbuild/bazel-gazelle/config"
	"github.com/bazelbuild/bazel-gazelle/language"
	"github.com/bazelbuild/bazel-gazelle/rule"
)

// TestImageFormulas locks in the per-kind formula table from
// IMAGE_PUBLISH_SPEC.md. Each canonical kind that emits :publish_image
// has one row: pkgPath + canonical name → expected attribute values.
// If you change one of the formulas, update the corresponding row here
// — that's the point. If you add a new binary kind to canonicalBindings,
// add it to imageFormulas AND add a row here.
func TestImageFormulas(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name       string
		kind       string
		pkgPath    string
		canonical  string
		appPrefix  string
		wantSuffix string
		wantStrip  string
		wantEntry  []string
	}{
		{
			name:       "java_binary appends _deploy.jar and emits java entrypoint",
			kind:       "java_binary",
			pkgPath:    "modules/java_app",
			canonical:  "java_app",
			appPrefix:  "app",
			wantSuffix: "_deploy.jar",
			wantStrip:  "modules/java_app",
			wantEntry:  []string{"java", "{runtime_args}", "-jar", "/app/java_app_deploy.jar"},
		},
		{
			name:       "go_binary strips package + name_ subdir",
			kind:       "go_binary",
			pkgPath:    "modules/go_app",
			canonical:  "go_app",
			appPrefix:  "app",
			wantSuffix: "",
			wantStrip:  "modules/go_app/go_app_",
			wantEntry:  []string{"/app/go_app"},
		},
		{
			name:       "rust_binary strips package + name_ subdir",
			kind:       "rust_binary",
			pkgPath:    "modules/rust_app",
			canonical:  "rust_app",
			appPrefix:  "app",
			wantSuffix: "",
			wantStrip:  "modules/rust_app/rust_app_",
			wantEntry:  []string{"/app/rust_app"},
		},
		{
			name:       "cc_binary strips package only",
			kind:       "cc_binary",
			pkgPath:    "modules/cpp_app",
			canonical:  "cpp_app",
			appPrefix:  "app",
			wantSuffix: "",
			wantStrip:  "modules/cpp_app",
			wantEntry:  []string{"/app/cpp_app"},
		},
		{
			name:       "py_binary strips package only",
			kind:       "py_binary",
			pkgPath:    "modules/python_app",
			canonical:  "python_app",
			appPrefix:  "app",
			wantSuffix: "",
			wantStrip:  "modules/python_app",
			wantEntry:  []string{"/app/python_app"},
		},
		{
			name:       "empty app_prefix lays binary at tar root",
			kind:       "cc_binary",
			pkgPath:    "modules/cpp_app",
			canonical:  "cpp_app",
			appPrefix:  "",
			wantSuffix: "",
			wantStrip:  "modules/cpp_app",
			wantEntry:  []string{"/cpp_app"},
		},
		{
			name:       "empty app_prefix on java still wires deploy.jar at root",
			kind:       "java_binary",
			pkgPath:    "modules/java_app",
			canonical:  "java_app",
			appPrefix:  "",
			wantSuffix: "_deploy.jar",
			wantStrip:  "modules/java_app",
			wantEntry:  []string{"java", "{runtime_args}", "-jar", "/java_app_deploy.jar"},
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			f, ok := imageFormulas[tc.kind]
			if !ok {
				t.Fatalf("imageFormulas missing entry for kind %q", tc.kind)
			}
			if f.binaryTargetSuffix != tc.wantSuffix {
				t.Errorf("binaryTargetSuffix: got %q, want %q", f.binaryTargetSuffix, tc.wantSuffix)
			}
			if got := f.stripPrefix(tc.pkgPath, tc.canonical); got != tc.wantStrip {
				t.Errorf("stripPrefix: got %q, want %q", got, tc.wantStrip)
			}
			if got := f.entrypoint(tc.appPrefix, tc.canonical); !reflect.DeepEqual(got, tc.wantEntry) {
				t.Errorf("entrypoint: got %v, want %v", got, tc.wantEntry)
			}
		})
	}
}

// TestCanonicalBindingsCoversImageFormulas guards against drift between
// the artifact-track binding table and the image-track formula table.
// Every binary kind in canonicalBindings must have a matching imageFormula;
// every imageFormula key must be a known binary kind. A mismatch is what
// triggers the runtime "kind X is a binary in canonicalBindings but has
// no image formula" warning — this test catches it at compile-test time.
func TestCanonicalBindingsCoversImageFormulas(t *testing.T) {
	t.Parallel()
	for kind, b := range canonicalBindings {
		if b.role != roleBinary {
			continue
		}
		if _, ok := imageFormulas[kind]; !ok {
			t.Errorf("canonicalBindings has binary kind %q but imageFormulas does not", kind)
		}
	}
	for kind := range imageFormulas {
		b, ok := canonicalBindings[kind]
		if !ok {
			t.Errorf("imageFormulas has %q but canonicalBindings does not", kind)
			continue
		}
		if b.role != roleBinary {
			t.Errorf("imageFormulas has %q but canonicalBindings classifies it as %q, not binary", kind, b.role)
		}
	}
}

// TestValidateImageAppPrefix locks in the parity between gazelle's
// pre-flight check and the image_publish macro's _validate_app_prefix.
// The two must agree — otherwise a malformed prefix passes gazelle and
// fails analysis at the next bazel build, hiding the source.
func TestValidateImageAppPrefix(t *testing.T) {
	t.Parallel()
	cases := []struct {
		prefix  string
		wantErr bool
	}{
		{"app", false},
		{"", false},
		{"deeply/nested/path", false},
		{"/app", true},
		{"app/", true},
		{"app/../etc", true},
		{"..", true},
		{"a/../b", true},
	}
	for _, tc := range cases {
		t.Run(tc.prefix, func(t *testing.T) {
			t.Parallel()
			err := validateImageAppPrefix(tc.prefix)
			if (err != nil) != tc.wantErr {
				t.Errorf("validateImageAppPrefix(%q): got err=%v, wantErr=%v", tc.prefix, err, tc.wantErr)
			}
		})
	}
}

// TestResolveImageConfigDefaults verifies the absence-of-key fallback
// for image_app_prefix (default "app") and the empty-table fallback for
// image_bases (empty map, never nil — so .Bases[k] lookups never panic).
func TestResolveImageConfigDefaults(t *testing.T) {
	t.Parallel()
	img, err := resolveImageConfig(publishConfig{})
	if err != nil {
		t.Fatalf("resolveImageConfig({}): %v", err)
	}
	if img.AppPrefix != defaultImageAppPrefix {
		t.Errorf("AppPrefix: got %q, want %q", img.AppPrefix, defaultImageAppPrefix)
	}
	if img.Bases == nil {
		t.Errorf("Bases: got nil, want empty map")
	}
}

// TestResolveImageConfigExplicitEmptyPrefix verifies that explicitly
// setting image_app_prefix = "" is honored (binary lands at tar root)
// rather than being silently replaced with the default.
func TestResolveImageConfigExplicitEmptyPrefix(t *testing.T) {
	t.Parallel()
	empty := ""
	img, err := resolveImageConfig(publishConfig{
		Conventions: conventions{ImageAppPrefix: &empty},
	})
	if err != nil {
		t.Fatalf("resolveImageConfig: %v", err)
	}
	if img.AppPrefix != "" {
		t.Errorf("AppPrefix: got %q, want \"\"", img.AppPrefix)
	}
}

// ---------------------------------------------------------------------------
// GenerateRules: opt-out routing into Gen / Empty (prune vs. freeze vs. warn).
// ---------------------------------------------------------------------------

// ccBinaryBuild is an in-scope cc_binary package that already carries both
// generated rules, so a test can observe whether each is regenerated, reaped,
// or left untouched.
const ccBinaryBuild = `cc_binary(name = "foo")

binary_bundle_publish(
    name = "publish",
    artifact_id = "foo",
    binary_target = ":foo",
)

image_publish(
    name = "publish_image",
    artifact_id = "foo",
    base = "@base",
    binary_target = ":foo",
)
`

func parseBuild(t *testing.T, rel, content string) *rule.File {
	t.Helper()
	f, err := rule.LoadData(filepath.Join(rel, "BUILD.bazel"), path.Base(rel), []byte(content))
	if err != nil {
		t.Fatalf("LoadData(%s): %v", rel, err)
	}
	return f
}

func ruleNames(rules []*rule.Rule) []string {
	if len(rules) == 0 {
		return nil // so DeepEqual against a nil "want" holds for the no-rules case
	}
	out := make([]string, 0, len(rules))
	for _, r := range rules {
		out = append(out, r.Name())
	}
	sort.Strings(out)
	return out
}

// langWithBase returns an extension with cc_binary's image base configured and
// every package in scope (empty PathPatterns), the common fixture state.
func langWithBase() *publishLang {
	return &publishLang{
		convLoaded: true,
		imgCfg:     imageConfig{AppPrefix: "app", Bases: map[string]string{"cc_binary": "@base"}},
	}
}

func assertResult(t *testing.T, res language.GenerateResult, wantGen, wantEmpty []string) {
	t.Helper()
	if got := ruleNames(res.Gen); !reflect.DeepEqual(got, wantGen) {
		t.Errorf("Gen: got %v, want %v", got, wantGen)
	}
	if got := ruleNames(res.Empty); !reflect.DeepEqual(got, wantEmpty) {
		t.Errorf("Empty: got %v, want %v", got, wantEmpty)
	}
}

func TestGenerateRules_Normal_GeneratesBothNoReap(t *testing.T) {
	t.Parallel()
	res := langWithBase().GenerateRules(language.GenerateArgs{
		File: parseBuild(t, "modules/foo", ccBinaryBuild), Rel: "modules/foo",
	})
	assertResult(t, res, []string{"publish", "publish_image"}, nil)
}

func TestGenerateRules_PublishIgnore_ReapsBoth(t *testing.T) {
	t.Parallel()
	p := langWithBase()
	p.ignored = map[string]bool{"modules/foo": true}
	res := p.GenerateRules(language.GenerateArgs{
		File: parseBuild(t, "modules/foo", ccBinaryBuild), Rel: "modules/foo",
	})
	assertResult(t, res, nil, []string{"publish", "publish_image"})
}

func TestGenerateRules_IgnoreArtifact_ReapsArtifactKeepsImage(t *testing.T) {
	t.Parallel()
	p := langWithBase()
	p.ignoredArtifact = map[string]bool{"modules/foo": true}
	res := p.GenerateRules(language.GenerateArgs{
		File: parseBuild(t, "modules/foo", ccBinaryBuild), Rel: "modules/foo",
	})
	assertResult(t, res, []string{"publish_image"}, []string{"publish"})
}

func TestGenerateRules_IgnoreImage_ReapsImageKeepsArtifact(t *testing.T) {
	t.Parallel()
	p := langWithBase()
	p.ignoredImage = map[string]bool{"modules/foo": true}
	res := p.GenerateRules(language.GenerateArgs{
		File: parseBuild(t, "modules/foo", ccBinaryBuild), Rel: "modules/foo",
	})
	assertResult(t, res, []string{"publish"}, []string{"publish_image"})
}

func TestGenerateRules_NoPublishTag_ReapsBoth(t *testing.T) {
	t.Parallel()
	build := `cc_binary(name = "foo", tags = ["no-publish"])

binary_bundle_publish(name = "publish", binary_target = ":foo")

image_publish(name = "publish_image", base = "@base", binary_target = ":foo")
`
	res := langWithBase().GenerateRules(language.GenerateArgs{
		File: parseBuild(t, "modules/foo", build), Rel: "modules/foo",
	})
	assertResult(t, res, nil, []string{"publish", "publish_image"})
}

func TestGenerateRules_IgnoreKeep_FreezesNoReap(t *testing.T) {
	t.Parallel()
	p := langWithBase()
	p.keep = map[string]bool{"modules/foo": true}
	res := p.GenerateRules(language.GenerateArgs{
		File: parseBuild(t, "modules/foo", ccBinaryBuild), Rel: "modules/foo",
	})
	assertResult(t, res, nil, nil)
}

func TestGenerateRules_MissingBase_DoesNotReapImage(t *testing.T) {
	t.Parallel()
	// No image base configured → image is skipped with a warning, but an
	// existing :publish_image must NOT be reaped (config gap ≠ opt-out).
	p := &publishLang{convLoaded: true, imgCfg: imageConfig{AppPrefix: "app", Bases: map[string]string{}}}
	res := p.GenerateRules(language.GenerateArgs{
		File: parseBuild(t, "modules/foo", ccBinaryBuild), Rel: "modules/foo",
	})
	assertResult(t, res, []string{"publish"}, nil)
}

func TestGenerateRules_OutOfScope_NoReap(t *testing.T) {
	t.Parallel()
	p := langWithBase()
	p.conv = conventions{PathPatterns: []string{"services/**"}}
	res := p.GenerateRules(language.GenerateArgs{
		File: parseBuild(t, "modules/foo", ccBinaryBuild), Rel: "modules/foo",
	})
	assertResult(t, res, nil, nil)
}

func TestGenerateRules_RemoveAll_ReapsAllIgnoringScope(t *testing.T) {
	t.Parallel()
	p := langWithBase()
	p.removeAll = true
	p.conv = conventions{PathPatterns: []string{"services/**"}} // out of scope, yet reaped
	res := p.GenerateRules(language.GenerateArgs{
		File: parseBuild(t, "modules/foo", ccBinaryBuild), Rel: "modules/foo",
	})
	assertResult(t, res, nil, []string{"publish", "publish_image"})
}

func TestGenerateRules_RemoveAll_RespectsKeep(t *testing.T) {
	t.Parallel()
	p := langWithBase()
	p.removeAll = true
	p.keep = map[string]bool{"modules/foo": true}
	res := p.GenerateRules(language.GenerateArgs{
		File: parseBuild(t, "modules/foo", ccBinaryBuild), Rel: "modules/foo",
	})
	assertResult(t, res, nil, nil)
}

func TestConfigure_RecordsKeepDirective(t *testing.T) {
	t.Parallel()
	p := &publishLang{}
	c := &config.Config{RepoRoot: t.TempDir()}
	f := parseBuild(t, "modules/foo", "# gazelle:publish_ignore_keep\n")
	p.Configure(c, "modules/foo", f)
	if !p.keep["modules/foo"] {
		t.Errorf("Configure did not record publish_ignore_keep directive")
	}
}
