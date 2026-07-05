# --- BEGIN lang:core ---
"""
This module contains all linters definition as per the rules_lint documentation
https://github.com/aspect-build/rules_lint/blob/main/docs/linting.md
"""
# --- END lang:core ---

# --- BEGIN lang:cpp ---
load("@aspect_rules_lint//lint:clang_tidy.bzl", "lint_clang_tidy_aspect")
# --- END lang:cpp ---

# --- BEGIN lang:core ---
load("@aspect_rules_lint//lint:lint_test.bzl", "lint_test")
# --- END lang:core ---

# --- BEGIN lang:java ---
load("@aspect_rules_lint//lint:pmd.bzl", "lint_pmd_aspect")
# --- END lang:java ---

# --- BEGIN lang:python ---
load("@aspect_rules_lint//lint:ruff.bzl", "lint_ruff_aspect")
# --- END lang:python ---

# --- BEGIN lang:java ---
load("@aspect_rules_lint//lint:spotbugs.bzl", "lint_spotbugs_aspect")
# --- END lang:java ---

# --- BEGIN lang:python ---
load("@aspect_rules_lint//lint:ty.bzl", "lint_ty_aspect")
# --- END lang:python ---

# --- BEGIN lang:rust ---
# Rust clippy uses rules_rust natively, not aspect_rules_lint. aspect_rules_lint
# dropped its umbrella clippy after 2.5.2; the replacement aspect_rules_lint_rust
# module sources rules_rust from rules_rs, so its clippy aspect silently no-ops
# against our BCR rules_rust targets (CrateInfo mismatch). See
# aspect-build/rules_lint#879.
load("@rules_rust//rust:defs.bzl", "rust_clippy")
load("@rules_shell//shell:sh_test.bzl", "sh_test")
# --- END lang:rust ---

# --- BEGIN lang:cpp ---
clang_tidy = lint_clang_tidy_aspect(
    binary = Label("//tools/lint:clang_tidy"),
    configs = [
        Label("//:.clang-tidy"),
    ],
    lint_target_headers = True,
    angle_includes_are_system = False,
    verbose = False,
)

clang_tidy_test = lint_test(aspect = clang_tidy)
# --- END lang:cpp ---

# --- BEGIN lang:rust ---
def clippy_test(name, srcs, tags = None, **kwargs):
    """Non-blocking native rules_rust clippy gate for a rust source rule.

    Runs clippy in capture mode (--@rules_rust//rust/settings:capture_clippy_output,
    set in .bazelrc) so the action never fails the build, then asserts the captured
    output is empty. Same red/green shape as the other lint_tests, tagged "lint".

    Args:
        name: the test target (gazelle emits "<src>.lint").
        srcs: a single-element list with the rust source rule to lint.
        tags: test tags (gazelle passes ["lint"]).
        **kwargs: forwarded to the sh_test (e.g. size).
    """
    clippy = "_{}.clippy".format(name)
    rust_clippy(
        name = clippy,
        # testonly so the clippy target can lint testonly sources (e.g. rust_test).
        testonly = True,
        deps = srcs,
        tags = ["manual"],
    )
    sh_test(
        name = name,
        srcs = ["//tools/lint:clippy_assert_empty.sh"],
        args = ["$(rootpath :{})".format(clippy)],
        data = [":" + clippy],
        tags = tags if tags != None else [],
        **kwargs
    )

# --- END lang:rust ---

# --- BEGIN lang:java ---
pmd = lint_pmd_aspect(
    binary = Label("//tools/lint:pmd"),
    rulesets = [Label("//:.pmd.xml")],
)

pmd_test = lint_test(aspect = pmd)

spotbugs = lint_spotbugs_aspect(
    binary = Label("//tools/lint:spotbugs"),
    exclude_filter = Label("//:.spotbugs-exclude.xml"),
)

spotbugs_test = lint_test(aspect = spotbugs)
# --- END lang:java ---

# --- BEGIN lang:python ---
ruff = lint_ruff_aspect(
    binary = Label("@aspect_rules_lint//lint:ruff_bin"),
    configs = [
        Label("//:.ruff.toml"),
    ],
)

ruff_test = lint_test(aspect = ruff)

ty = lint_ty_aspect(
    binary = Label("@aspect_rules_lint//lint:ty_bin"),
    config = Label("//:ty.toml"),
)

ty_test = lint_test(aspect = ty)
# --- END lang:python ---
