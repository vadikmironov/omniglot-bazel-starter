load("@rules_shell//shell:sh_test.bzl", "sh_test")

# Smoke test for the hermetic lcov genhtml renderer used by //tools/coverage:report.
# Renders a checked-in LCOV fixture and asserts the HTML output, so a Renovate bump
# to rules_perl / the pinned lcov archive that breaks genhtml fails here.
sh_test(
    name = "render_smoke_test",
    size = "small",
    srcs = ["render_smoke_test.sh"],
    args = [
        "$(rlocationpath @lcov//:genhtml)",
        "$(rlocationpath testdata/sample.lcov)",
    ],
    data = [
        "testdata/sample.lcov",
        "@lcov//:genhtml",
    ],
    deps = ["@rules_shell//shell/runfiles"],
)
