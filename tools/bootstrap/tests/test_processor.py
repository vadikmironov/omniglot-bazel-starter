"""Unit tests for bootstrap.processor — section filtering logic."""

import textwrap
import unittest

from bootstrap.processor import (
    extract_user_region,
    filter_sections,
    has_user_region,
    splice_user_region,
)


class TestCoreSection(unittest.TestCase):
    """lang:core sections are always included regardless of language selection."""

    def test_core_always_included(self) -> None:
        content = textwrap.dedent("""\
            # --- BEGIN lang:core ---
            core_line
            # --- END lang:core ---
        """)
        result = filter_sections(content, set())
        self.assertIn("core_line", result)

    def test_core_included_with_unrelated_selection(self) -> None:
        content = textwrap.dedent("""\
            # --- BEGIN lang:core ---
            always here
            # --- END lang:core ---
        """)
        result = filter_sections(content, {"python"})
        self.assertIn("always here", result)


class TestExcludeSection(unittest.TestCase):
    """exclude sections are always removed regardless of language selection."""

    def test_exclude_always_excluded(self) -> None:
        content = textwrap.dedent("""\
            # --- BEGIN exclude ---
            should be gone
            # --- END exclude ---
        """)
        result = filter_sections(content, {"python", "cpp", "rust", "java", "go"})
        self.assertNotIn("should be gone", result)

    def test_exclude_with_empty_selection(self) -> None:
        content = textwrap.dedent("""\
            # --- BEGIN exclude ---
            still gone
            # --- END exclude ---
        """)
        result = filter_sections(content, set())
        self.assertNotIn("still gone", result)


class TestLanguageSelection(unittest.TestCase):
    """Language sections are included/excluded based on selected_languages."""

    def test_selected_language_included(self) -> None:
        content = textwrap.dedent("""\
            # --- BEGIN lang:python ---
            python_content
            # --- END lang:python ---
        """)
        result = filter_sections(content, {"python"})
        self.assertIn("python_content", result)

    def test_unselected_language_excluded(self) -> None:
        content = textwrap.dedent("""\
            # --- BEGIN lang:python ---
            python_content
            # --- END lang:python ---
        """)
        result = filter_sections(content, {"cpp"})
        self.assertNotIn("python_content", result)

    def test_multiple_sections_mixed_selection(self) -> None:
        content = textwrap.dedent("""\
            # --- BEGIN lang:python ---
            python_line
            # --- END lang:python ---
            # --- BEGIN lang:cpp ---
            cpp_line
            # --- END lang:cpp ---
            # --- BEGIN lang:rust ---
            rust_line
            # --- END lang:rust ---
        """)
        result = filter_sections(content, {"python", "rust"})
        self.assertIn("python_line", result)
        self.assertNotIn("cpp_line", result)
        self.assertIn("rust_line", result)


class TestFeatureSelection(unittest.TestCase):
    """feature:X sections are included/excluded based on selected_features."""

    def test_selected_feature_included(self) -> None:
        content = textwrap.dedent("""\
            # --- BEGIN feature:publish ---
            publish_content
            # --- END feature:publish ---
        """)
        result = filter_sections(content, set(), {"publish"})
        self.assertIn("publish_content", result)

    def test_unselected_feature_excluded(self) -> None:
        content = textwrap.dedent("""\
            # --- BEGIN feature:publish ---
            publish_content
            # --- END feature:publish ---
        """)
        result = filter_sections(content, set(), set())
        self.assertNotIn("publish_content", result)

    def test_feature_independent_of_language(self) -> None:
        content = textwrap.dedent("""\
            # --- BEGIN lang:python ---
            python_line
            # --- END lang:python ---
            # --- BEGIN feature:publish ---
            publish_line
            # --- END feature:publish ---
        """)
        result = filter_sections(content, {"python"}, set())
        self.assertIn("python_line", result)
        self.assertNotIn("publish_line", result)

    def test_feature_multi_tag_or_logic(self) -> None:
        content = textwrap.dedent("""\
            # --- BEGIN feature:publish,telemetry ---
            shared_line
            # --- END feature:publish,telemetry ---
        """)
        self.assertIn("shared_line", filter_sections(content, set(), {"publish"}))
        self.assertIn("shared_line", filter_sections(content, set(), {"telemetry"}))
        self.assertNotIn("shared_line", filter_sections(content, set(), {"other"}))

    def test_features_default_to_empty(self) -> None:
        """Omitting the selected_features arg means no feature sections fire."""
        content = textwrap.dedent("""\
            # --- BEGIN feature:publish ---
            publish_content
            # --- END feature:publish ---
        """)
        result = filter_sections(content, set())  # no features kwarg
        self.assertNotIn("publish_content", result)


class TestMultiTagOrLogic(unittest.TestCase):
    """Multi-tag sections like lang:cpp,java use OR logic."""

    def test_multi_tag_first_selected(self) -> None:
        content = textwrap.dedent("""\
            # --- BEGIN lang:cpp,java ---
            shared_content
            # --- END lang:cpp,java ---
        """)
        result = filter_sections(content, {"cpp"})
        self.assertIn("shared_content", result)

    def test_multi_tag_second_selected(self) -> None:
        content = textwrap.dedent("""\
            # --- BEGIN lang:cpp,java ---
            shared_content
            # --- END lang:cpp,java ---
        """)
        result = filter_sections(content, {"java"})
        self.assertIn("shared_content", result)

    def test_multi_tag_both_selected(self) -> None:
        content = textwrap.dedent("""\
            # --- BEGIN lang:cpp,java ---
            shared_content
            # --- END lang:cpp,java ---
        """)
        result = filter_sections(content, {"cpp", "java"})
        self.assertIn("shared_content", result)

    def test_multi_tag_none_selected(self) -> None:
        content = textwrap.dedent("""\
            # --- BEGIN lang:cpp,java ---
            shared_content
            # --- END lang:cpp,java ---
        """)
        result = filter_sections(content, {"python"})
        self.assertNotIn("shared_content", result)


class TestMultiConditionAnd(unittest.TestCase):
    """Space-separated predicates in one tag are ANDed; comma stays OR within one."""

    CONTENT = textwrap.dedent("""\
        # --- BEGIN feature:lint lang:python ---
        mypy_line
        # --- END feature:lint lang:python ---
    """)

    def test_both_conditions_met(self) -> None:
        self.assertIn("mypy_line", filter_sections(self.CONTENT, {"python"}, {"lint"}))

    def test_feature_missing(self) -> None:
        self.assertNotIn("mypy_line", filter_sections(self.CONTENT, {"python"}, set()))

    def test_language_missing(self) -> None:
        self.assertNotIn("mypy_line", filter_sections(self.CONTENT, {"go"}, {"lint"}))

    def test_neither_met(self) -> None:
        self.assertNotIn("mypy_line", filter_sections(self.CONTENT, {"go"}, set()))

    def test_feature_and_feature(self) -> None:
        content = textwrap.dedent("""\
            # --- BEGIN feature:lint feature:publish ---
            both_line
            # --- END feature:lint feature:publish ---
        """)
        self.assertIn("both_line", filter_sections(content, set(), {"lint", "publish"}))
        self.assertNotIn("both_line", filter_sections(content, set(), {"lint"}))
        self.assertNotIn("both_line", filter_sections(content, set(), {"publish"}))

    def test_or_binds_tighter_than_and(self) -> None:
        """Comma (OR) is evaluated within a predicate; space (AND) across predicates."""
        content = textwrap.dedent("""\
            # --- BEGIN lang:cpp,java feature:lint ---
            x
            # --- END lang:cpp,java feature:lint ---
        """)
        self.assertIn("x", filter_sections(content, {"cpp"}, {"lint"}))
        self.assertIn("x", filter_sections(content, {"java"}, {"lint"}))
        self.assertNotIn("x", filter_sections(content, {"cpp"}, set()))
        self.assertNotIn("x", filter_sections(content, {"python"}, {"lint"}))

    def test_end_marker_whitespace_insensitive(self) -> None:
        content = "# --- BEGIN feature:lint  lang:python ---\nx\n# --- END feature:lint lang:python ---\n"
        self.assertIn("x", filter_sections(content, {"python"}, {"lint"}))


class TestMarkerStripping(unittest.TestCase):
    """All marker comment lines must be removed from output."""

    def test_markers_stripped(self) -> None:
        content = textwrap.dedent("""\
            # --- BEGIN lang:core ---
            content
            # --- END lang:core ---
        """)
        result = filter_sections(content, set())
        self.assertNotIn("BEGIN", result)
        self.assertNotIn("END", result)
        self.assertIn("content", result)

    def test_all_marker_variants_stripped(self) -> None:
        content = textwrap.dedent("""\
            # --- BEGIN lang:core ---
            a
            # --- END lang:core ---
            # --- BEGIN lang:python ---
            b
            # --- END lang:python ---
            # --- BEGIN lang:cpp,java ---
            c
            # --- END lang:cpp,java ---
            # --- BEGIN exclude ---
            d
            # --- END exclude ---
        """)
        result = filter_sections(content, {"python", "cpp", "java"})
        self.assertNotIn("---", result)


class TestBlankLineCollapse(unittest.TestCase):
    """Runs of 3+ consecutive blank lines are collapsed to 2."""

    def test_three_blank_lines_collapsed(self) -> None:
        content = "a\n\n\n\nb\n"
        result = filter_sections(content, set())
        self.assertEqual(result, "a\n\nb\n")

    def test_two_blank_lines_preserved(self) -> None:
        content = "a\n\nb\n"
        result = filter_sections(content, set())
        self.assertEqual(result, "a\n\nb\n")

    def test_collapse_after_section_removal(self) -> None:
        """When an unselected section is removed, resulting blank runs collapse."""
        content = textwrap.dedent("""\
            # --- BEGIN lang:core ---
            before
            # --- END lang:core ---

            # --- BEGIN lang:python ---
            python_stuff
            # --- END lang:python ---

            # --- BEGIN lang:core ---
            after
            # --- END lang:core ---
        """)
        result = filter_sections(content, {"cpp"})
        self.assertIn("before", result)
        self.assertIn("after", result)
        self.assertNotIn("python_stuff", result)
        # Should not have excessive blank lines
        self.assertNotIn("\n\n\n", result)

    def test_no_dangling_blank_before_closing_bracket(self) -> None:
        """A removed section that ends a brace/paren group leaves no blank
        before the closing bracket (gofmt-dirty output, seen with directives.go
        when feature:publish was stripped)."""
        content = textwrap.dedent("""\
            const (
            \t# --- BEGIN feature:lint ---
            \tLintIgnore = "lint_ignore"
            \t# --- END feature:lint ---

            \t# --- BEGIN feature:publish ---
            \tPublishIgnore = "publish_ignore"
            \t# --- END feature:publish ---
            )
        """)
        result = filter_sections(content, set(), {"lint"})
        self.assertIn("lint_ignore", result)
        self.assertNotIn("publish_ignore", result)
        self.assertNotIn("\n\n)", result)

    def test_separator_kept_when_a_later_section_survives(self) -> None:
        """A blank separating kept content from a removed section must survive
        when a *later* section is still included — removing it would merge gofmt
        alignment groups (the kinds.go regression: loadLinters vs kindRuffTest)."""
        content = textwrap.dedent("""\
            const (
            \tloadLinters = "x"

            \t# --- BEGIN lang:cpp ---
            \tkindCpp = "cpp"
            \t# --- END lang:cpp ---
            \t# --- BEGIN lang:python ---
            \tkindPy = "py"
            \t# --- END lang:python ---
            )
        """)
        result = filter_sections(content, {"python"})
        self.assertNotIn("kindCpp", result)
        # The separator survives: loadLinters is not merged into the kind group.
        self.assertIn('loadLinters = "x"\n\n\tkindPy', result)


class TestUntaggedContent(unittest.TestCase):
    """Lines outside any section are included by default."""

    def test_untagged_lines_between_sections(self) -> None:
        content = textwrap.dedent("""\
            # --- BEGIN lang:core ---
            core
            # --- END lang:core ---
            untagged separator
            # --- BEGIN lang:python ---
            python
            # --- END lang:python ---
        """)
        result = filter_sections(content, {"python"})
        self.assertIn("core", result)
        self.assertIn("untagged separator", result)
        self.assertIn("python", result)

    def test_untagged_preserved_even_without_selection(self) -> None:
        content = "just plain text\nno markers here\n"
        result = filter_sections(content, set())
        self.assertEqual(result, "just plain text\nno markers here\n")


class TestTrailingNewline(unittest.TestCase):
    """Output files end with exactly one newline (no trailing blank lines)."""

    def test_no_trailing_blank_line(self) -> None:
        content = textwrap.dedent("""\
            # --- BEGIN lang:core ---
            content
            # --- END lang:core ---
            # --- BEGIN lang:python ---
            python_stuff
            # --- END lang:python ---
        """)
        result = filter_sections(content, {"python"})
        self.assertTrue(result.endswith("\n"), "should end with newline")
        self.assertFalse(result.endswith("\n\n"), "should not end with blank line")

    def test_trailing_excluded_section(self) -> None:
        """When the last section is excluded, no trailing blank line remains."""
        content = textwrap.dedent("""\
            # --- BEGIN lang:core ---
            core_content
            # --- END lang:core ---

            # --- BEGIN lang:go ---
            go_content
            # --- END lang:go ---
        """)
        result = filter_sections(content, {"python"})
        self.assertIn("core_content", result)
        self.assertFalse(result.endswith("\n\n"), "should not end with blank line")


class TestSlashSlashMarkers(unittest.TestCase):
    """Support // comment markers (e.g., for go.mod files)."""

    def test_slash_slash_exclude(self) -> None:
        content = textwrap.dedent("""\
            require github.com/stretchr/testify v1.11.1

            // --- BEGIN exclude ---
            require golang.org/x/net v0.52.0
            // --- END exclude ---
        """)
        result = filter_sections(content, {"go"})
        self.assertIn("testify", result)
        self.assertNotIn("golang.org/x/net", result)

    def test_slash_slash_language_section(self) -> None:
        content = textwrap.dedent("""\
            // --- BEGIN lang:go ---
            go_content
            // --- END lang:go ---
        """)
        result = filter_sections(content, {"go"})
        self.assertIn("go_content", result)

        result = filter_sections(content, {"python"})
        self.assertNotIn("go_content", result)


class TestEdgeCases(unittest.TestCase):
    """Edge cases: empty input, no markers, nested sections."""

    def test_empty_input(self) -> None:
        result = filter_sections("", set())
        self.assertEqual(result, "")

    def test_no_markers(self) -> None:
        content = "line1\nline2\nline3\n"
        result = filter_sections(content, {"python"})
        self.assertEqual(result, content)

    def test_nested_sections_rejected(self) -> None:
        """Nested section markers raise ValueError."""
        content = textwrap.dedent("""\
            # --- BEGIN lang:core ---
            outer_core
            # --- BEGIN lang:python ---
            inner_python
            # --- END lang:python ---
            still_core
            # --- END lang:core ---
        """)
        with self.assertRaises(ValueError) as ctx:
            filter_sections(content, {"python"})
        self.assertIn("Nested section markers", str(ctx.exception))
        self.assertIn("lang:python", str(ctx.exception))
        self.assertIn("lang:core", str(ctx.exception))

    def test_nested_sections_error_includes_filename(self) -> None:
        """ValueError message includes filename when provided."""
        content = textwrap.dedent("""\
            # --- BEGIN lang:java ---
            # --- BEGIN lang:python ---
            # --- END lang:python ---
            # --- END lang:java ---
        """)
        with self.assertRaises(ValueError) as ctx:
            filter_sections(content, {"python"}, filename="tools/lint/linters.bzl")
        self.assertIn("tools/lint/linters.bzl", str(ctx.exception))

    def test_mismatched_end_raises(self) -> None:
        """An END whose tag differs from the open BEGIN raises."""
        content = textwrap.dedent("""\
            # --- BEGIN lang:python ---
            x
            # --- END lang:cpp ---
        """)
        with self.assertRaises(ValueError) as ctx:
            filter_sections(content, {"python"})
        self.assertIn("Mismatched", str(ctx.exception))

    def test_unclosed_section_raises(self) -> None:
        """A BEGIN with no matching END raises."""
        with self.assertRaises(ValueError) as ctx:
            filter_sections("# --- BEGIN lang:python ---\nx\n", {"python"})
        self.assertIn("Unclosed", str(ctx.exception))

    def test_stray_end_raises(self) -> None:
        """An END with no open section raises."""
        with self.assertRaises(ValueError) as ctx:
            filter_sections("x\n# --- END lang:python ---\n", {"python"})
        self.assertIn("Unbalanced", str(ctx.exception))


class TestAllFiveLanguages(unittest.TestCase):
    """Test filtering with all five language sections present."""

    CONTENT = textwrap.dedent("""\
        # --- BEGIN lang:core ---
        core_content
        # --- END lang:core ---
        # --- BEGIN lang:python ---
        python_content
        # --- END lang:python ---
        # --- BEGIN lang:cpp ---
        cpp_content
        # --- END lang:cpp ---
        # --- BEGIN lang:rust ---
        rust_content
        # --- END lang:rust ---
        # --- BEGIN lang:java ---
        java_content
        # --- END lang:java ---
        # --- BEGIN lang:go ---
        go_content
        # --- END lang:go ---
    """)

    ALL_LANGS = {"python", "cpp", "rust", "java", "go"}

    def test_all_selected(self) -> None:
        result = filter_sections(self.CONTENT, self.ALL_LANGS)
        for lang in self.ALL_LANGS:
            self.assertIn(f"{lang}_content", result)
        self.assertIn("core_content", result)

    def test_single_language_only(self) -> None:
        for lang in self.ALL_LANGS:
            result = filter_sections(self.CONTENT, {lang})
            self.assertIn("core_content", result)
            self.assertIn(f"{lang}_content", result)
            for other in self.ALL_LANGS - {lang}:
                self.assertNotIn(f"{other}_content", result)


class TestRealSnippets(unittest.TestCase):
    """Tests using fragments from actual composite files in the repo."""

    def test_real_module_bazel_snippet(self) -> None:
        """Fragment resembling MODULE.bazel with include() lines."""
        content = textwrap.dedent("""\
            # --- BEGIN lang:core ---
            module(
                name = "omniglot-bazel-starter",
                version = "0.0.1",
            )
            bazel_dep(name = "aspect_rules_lint", version = "2.1.0")
            # --- END lang:core ---

            # --- BEGIN lang:python ---
            include("//tools/python:python_segment.MODULE.bazel")
            # --- END lang:python ---

            # --- BEGIN lang:cpp,java ---
            include("//tools/cpp:llvm_segment.MODULE.bazel")
            # --- END lang:cpp,java ---

            # --- BEGIN lang:cpp ---
            include("//tools/cpp:cpp_segment.MODULE.bazel")
            # --- END lang:cpp ---

            # --- BEGIN lang:java ---
            include("//tools/java:java_segment.MODULE.bazel")
            # --- END lang:java ---
        """)
        # Java only: should get core + llvm + java, no python/cpp
        result = filter_sections(content, {"java"})
        self.assertIn("module(", result)
        self.assertIn("llvm_segment", result)
        self.assertIn("java_segment", result)
        self.assertNotIn("python_segment", result)
        self.assertNotIn("cpp_segment", result)

    def test_real_bazelrc_snippet(self) -> None:
        """Fragment resembling .bazelrc with config blocks."""
        content = textwrap.dedent("""\
            # --- BEGIN lang:core ---
            common --enable_platform_specific_config
            # --- END lang:core ---

            # --- BEGIN lang:cpp ---
            build:gcc_host --repo_env=CC=gcc
            build:clang_host --repo_env=CC=clang
            # --- END lang:cpp ---

            # --- BEGIN lang:python ---
            common:python3_13_host --@rules_python//python/config_settings:python_version=3.13
            # --- END lang:python ---
        """)
        result = filter_sections(content, {"python"})
        self.assertIn("enable_platform_specific_config", result)
        self.assertIn("python3_13_host", result)
        self.assertNotIn("gcc_host", result)

    def test_real_format_build_snippet(self) -> None:
        """Fragment resembling tools/format/BUILD with mid-function tags."""
        content = textwrap.dedent("""\
            # --- BEGIN lang:core ---
            load("@aspect_rules_lint//format:defs.bzl", "format_multirun")
            # --- END lang:core ---

            # --- BEGIN lang:core ---
            format_multirun(
                name = "format",
            # --- END lang:core ---
                # --- BEGIN lang:cpp ---
                c = "@llvm_toolchain_llvm//:bin/clang-format",
                cc = "@llvm_toolchain_llvm//:bin/clang-format",
                # --- END lang:cpp ---
                # --- BEGIN lang:python ---
                python = "@aspect_rules_lint//format:ruff",
                # --- END lang:python ---
                # --- BEGIN lang:rust ---
                rust = "@rules_rust//tools/upstream_wrapper:rustfmt",
                # --- END lang:rust ---
                # --- BEGIN lang:core ---
                visibility = ["//visibility:public"],
            )
            # --- END lang:core ---
        """)
        # Python + Rust selected
        result = filter_sections(content, {"python", "rust"})
        self.assertIn("format_multirun", result)
        self.assertIn("format:ruff", result)
        self.assertIn("rustfmt", result)
        self.assertNotIn("clang-format", result)
        self.assertIn("visibility", result)

    def test_real_lint_sh_snippet(self) -> None:
        """Fragment resembling tools/lint/lint.sh with aspects array."""
        content = textwrap.dedent("""\
            # --- BEGIN lang:core ---
            aspects=()
            # --- END lang:core ---
            # --- BEGIN lang:python ---
            aspects+=(//tools/lint:linters.bzl%ruff)
            # --- END lang:python ---
            # --- BEGIN lang:cpp ---
            aspects+=(//tools/lint:linters.bzl%clang_tidy)
            # --- END lang:cpp ---
            # --- BEGIN lang:rust ---
            aspects+=(//tools/lint:linters.bzl%clippy)
            # --- END lang:rust ---
            # --- BEGIN lang:java ---
            aspects+=(//tools/lint:linters.bzl%pmd //tools/lint:linters.bzl%spotbugs)
            # --- END lang:java ---
            # --- BEGIN lang:core ---
            IFS=','; aspects_str="${aspects[*]}"; unset IFS
            # --- END lang:core ---
        """)
        result = filter_sections(content, {"python", "java"})
        self.assertIn("aspects=()", result)
        self.assertIn("ruff", result)
        self.assertIn("pmd", result)
        self.assertIn("spotbugs", result)
        self.assertNotIn("clang_tidy", result)
        self.assertNotIn("clippy", result)
        self.assertIn("aspects_str", result)


class TestExtractUserRegion(unittest.TestCase):
    """extract_user_region returns the body, or None for ambiguous shapes."""

    def test_returns_body_between_markers(self) -> None:
        content = textwrap.dedent("""\
            before
            # --- BEGIN user-managed ---
            flask
            requests
            # --- END user-managed ---
            after
        """)
        self.assertEqual(extract_user_region(content), "flask\nrequests\n")

    def test_empty_region(self) -> None:
        content = textwrap.dedent("""\
            # --- BEGIN user-managed ---
            # --- END user-managed ---
        """)
        self.assertEqual(extract_user_region(content), "")

    def test_no_markers_returns_none(self) -> None:
        self.assertIsNone(extract_user_region("just\ncontent\n"))

    def test_only_begin_returns_none(self) -> None:
        self.assertIsNone(extract_user_region("# --- BEGIN user-managed ---\nx\n"))

    def test_only_end_returns_none(self) -> None:
        self.assertIsNone(extract_user_region("x\n# --- END user-managed ---\n"))

    def test_duplicate_begin_returns_none(self) -> None:
        content = textwrap.dedent("""\
            # --- BEGIN user-managed ---
            a
            # --- BEGIN user-managed ---
            b
            # --- END user-managed ---
        """)
        self.assertIsNone(extract_user_region(content))

    def test_slash_slash_markers(self) -> None:
        content = textwrap.dedent("""\
            // --- BEGIN user-managed ---
            require example.com/x v1
            // --- END user-managed ---
        """)
        self.assertEqual(extract_user_region(content), "require example.com/x v1\n")

    def test_html_comment_markers(self) -> None:
        """Markdown HTML-comment markers are recognised (used by the README)."""
        content = textwrap.dedent("""\
            intro
            <!-- --- BEGIN user-managed --- -->
            my description
            <!-- --- END user-managed --- -->
            outro
        """)
        self.assertEqual(extract_user_region(content), "my description\n")
        self.assertTrue(has_user_region(content))

    def test_has_user_region(self) -> None:
        self.assertTrue(has_user_region("# --- BEGIN user-managed ---\n# --- END user-managed ---\n"))
        self.assertTrue(has_user_region("<!-- --- BEGIN user-managed --- -->\n<!-- --- END user-managed --- -->\n"))
        self.assertFalse(has_user_region("nope\n"))


class TestSpliceUserRegion(unittest.TestCase):
    """splice_user_region carries the existing body under freshly rendered markers."""

    RENDERED = textwrap.dedent("""\
        [dependencies]
        # --- BEGIN user-managed ---
        # Your crates here. Preserved across re-bootstrap.
        # --- END user-managed ---
    """)

    def test_existing_body_replaces_seed(self) -> None:
        existing = textwrap.dedent("""\
            [dependencies]
            # --- BEGIN user-managed ---
            serde = "1"
            # --- END user-managed ---
        """)
        result = splice_user_region(self.RENDERED, existing)
        self.assertIn('serde = "1"', result)
        self.assertNotIn("Your crates here", result)

    def test_fresh_markers_kept(self) -> None:
        existing = '# --- BEGIN user-managed ---\nserde = "1"\n# --- END user-managed ---\n'
        result = splice_user_region(self.RENDERED, existing)
        self.assertIn("# --- BEGIN user-managed ---", result)
        self.assertIn("# --- END user-managed ---", result)
        self.assertTrue(result.startswith("[dependencies]\n"))

    def test_starter_baseline_refreshed_with_user_body_kept(self) -> None:
        rendered = textwrap.dedent("""\
            ruff
            mypy
            # --- BEGIN user-managed ---
            seed
            # --- END user-managed ---
        """)
        existing = textwrap.dedent("""\
            ruff
            # --- BEGIN user-managed ---
            flask
            # --- END user-managed ---
        """)
        result = splice_user_region(rendered, existing)
        self.assertIn("mypy", result)  # refreshed starter baseline
        self.assertIn("flask", result)  # preserved user body
        self.assertNotIn("seed", result)

    def test_existing_without_region_returns_rendered(self) -> None:
        self.assertEqual(splice_user_region(self.RENDERED, "no markers here\n"), self.RENDERED)

    def test_idempotent_when_bodies_match(self) -> None:
        self.assertEqual(splice_user_region(self.RENDERED, self.RENDERED), self.RENDERED)

    def test_html_comment_marker_splice(self) -> None:
        """The README's HTML-comment region splices like the # / // forms."""
        rendered = textwrap.dedent("""\
            # title

            <!-- --- BEGIN user-managed --- -->
            seed description
            <!-- --- END user-managed --- -->

            ## Install
        """)
        existing = textwrap.dedent("""\
            # title

            <!-- --- BEGIN user-managed --- -->
            my real project description
            <!-- --- END user-managed --- -->

            ## Install (stale)
        """)
        result = splice_user_region(rendered, existing)
        self.assertIn("my real project description", result)  # user body kept
        self.assertNotIn("seed description", result)
        self.assertIn("## Install\n", result)  # rendered baseline kept
        self.assertNotIn("stale", result)


class TestUserRegionSurvivesFilter(unittest.TestCase):
    """filter_sections leaves user-managed markers intact while consuming exclude."""

    def test_user_markers_pass_through_exclude_stripped(self) -> None:
        content = textwrap.dedent("""\
            ruff
            # --- BEGIN user-managed ---
            # your deps
            # --- END user-managed ---
            # --- BEGIN exclude ---
            questionary
            # --- END exclude ---
        """)
        result = filter_sections(content, {"python"})
        self.assertIn("# --- BEGIN user-managed ---", result)
        self.assertIn("# --- END user-managed ---", result)
        self.assertNotIn("questionary", result)
        self.assertTrue(has_user_region(result))

    def test_html_user_markers_survive_filter(self) -> None:
        """A README's HTML user-managed markers pass through filter_sections
        unchanged while its lang/feature sections are consumed."""
        content = textwrap.dedent("""\
            <!-- --- BEGIN user-managed --- -->
            keep me
            <!-- --- END user-managed --- -->
            # --- BEGIN feature:publish ---
            publish docs
            # --- END feature:publish ---
        """)
        result = filter_sections(content, set(), set())
        self.assertIn("<!-- --- BEGIN user-managed --- -->", result)
        self.assertIn("keep me", result)
        self.assertNotIn("publish docs", result)
        self.assertTrue(has_user_region(result))


if __name__ == "__main__":
    unittest.main()
