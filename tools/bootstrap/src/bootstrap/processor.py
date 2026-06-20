"""Composite file section filter.

Parses files with section markers and produces output containing only
the sections relevant to the selected languages and features.

Marker format:
    # --- BEGIN lang:core ---
    # --- BEGIN lang:python ---
    # --- BEGIN lang:cpp,java ---
    # --- BEGIN feature:publish ---
    # --- BEGIN feature:lint lang:python ---
    # --- BEGIN exclude ---
    # --- END lang:core ---
    # --- END feature:publish ---
    # --- END exclude ---

A tag is one or more space-separated predicates (``lang:*``, ``feature:*`` or
``exclude``). Two operators with distinct precedence combine them:

    comma  → OR within a predicate   lang:cpp,java       = cpp OR java
    space  → AND between predicates   feature:lint lang:python = lint AND python

So ``lang:cpp,java feature:lint`` means "(cpp OR java) AND lint". Sections
must not nest; a two-condition tag expresses what nesting otherwise would.
The END marker must repeat the BEGIN tag (whitespace-insensitive).
"""

import re

_PREDICATE = r"(?:(?:lang|feature):\S+|exclude)"
_TAG = rf"{_PREDICATE}(?:\s+{_PREDICATE})*"
_BEGIN_RE = re.compile(rf"^\s*(?:#|//)\s*---\s*BEGIN\s+({_TAG})\s*---\s*$")
_END_RE = re.compile(rf"^\s*(?:#|//)\s*---\s*END\s+({_TAG})\s*---\s*$")


def _predicate_included(predicate: str, selected_languages: set[str], selected_features: set[str]) -> bool:
    """Decide whether a single predicate matches the current selection.

    ``exclude`` never matches; ``lang:core`` always does; ``lang:<tags>`` and
    ``feature:<tags>`` match when any comma-separated tag is selected (OR).
    """
    if predicate == "exclude":
        return False
    if predicate == "lang:core":
        return True
    if predicate.startswith("lang:"):
        langs = predicate.removeprefix("lang:").split(",")
        return any(lang in selected_languages for lang in langs)
    feats = predicate.removeprefix("feature:").split(",")
    return any(feat in selected_features for feat in feats)


def _section_included(tag: str, selected_languages: set[str], selected_features: set[str]) -> bool:
    """A space-separated tag is included only when every predicate matches (AND)."""
    return all(_predicate_included(p, selected_languages, selected_features) for p in tag.split())


def filter_sections(
    content: str,
    selected_languages: set[str],
    selected_features: set[str] | None = None,
    *,
    filename: str = "",
) -> str:
    """Filter a composite file based on selected languages and features.

    - Always includes ``lang:core`` sections.
    - Always excludes ``exclude`` sections.
    - Includes ``lang:<tags>`` sections when any tag matches *selected_languages*.
    - Includes ``feature:<tags>`` sections when any tag matches *selected_features*.
    - Includes a multi-predicate tag only when every predicate matches (AND).
    - Strips all marker comment lines from the output.
    - Collapses runs of 3+ consecutive blank lines down to 2.
    - Drops blank lines stranded immediately before a closing-bracket line
      (e.g. when a section ending a brace/paren group is removed) — the one
      gofmt-visible artifact stripping introduces. Separator blanks between
      surviving content are left untouched (gofmt keeps those).
    - Raises ``ValueError`` on nested markers, a stray/mismatched END, or a
      BEGIN left unclosed at end of file.
    """
    selected_features = selected_features or set()

    lines = content.splitlines(keepends=True)
    result: list[str] = []
    current_tag: str | None = None  # normalized tag of the open section, else None
    include = True

    for line_num, line in enumerate(lines, start=1):
        begin_match = _BEGIN_RE.match(line)
        if begin_match:
            tag = " ".join(begin_match.group(1).split())  # normalize inner whitespace
            if current_tag is not None:
                loc = f" in {filename}" if filename else ""
                raise ValueError(
                    f"Nested section markers are not supported{loc}: "
                    f"found BEGIN {tag} at line {line_num} while already inside {current_tag}. "
                    f"Use a multi-condition tag (e.g. 'feature:lint lang:python') instead of nesting."
                )
            current_tag = tag
            include = _section_included(tag, selected_languages, selected_features)
            continue  # strip the marker line

        end_match = _END_RE.match(line)
        if end_match:
            tag = " ".join(end_match.group(1).split())
            if current_tag is None:
                loc = f" in {filename}" if filename else ""
                raise ValueError(f"Unbalanced END {tag}{loc} at line {line_num}: no open section")
            if tag != current_tag:
                loc = f" in {filename}" if filename else ""
                raise ValueError(f"Mismatched section markers{loc}: END {tag} at line {line_num} closes {current_tag}")
            current_tag = None
            include = True
            continue  # strip the marker line

        # Lines outside any section (e.g. blank separators between sections)
        # are included by default. Inside a section, respect the inclusion decision.
        if current_tag is None or include:
            result.append(line)

    if current_tag is not None:
        loc = f" in {filename}" if filename else ""
        raise ValueError(f"Unclosed section {current_tag}{loc} at end of {filename or 'content'}")

    text = _collapse_blank_lines("".join(result))
    text = _drop_blanks_before_closers(text)
    # Ensure exactly one trailing newline (no trailing blank lines)
    return text.rstrip("\n") + "\n" if text else text


def _collapse_blank_lines(text: str) -> str:
    """Collapse runs of 3+ consecutive blank lines down to 2."""
    return re.sub(r"\n{3,}", "\n\n", text)


def _is_closing_bracket_line(line: str) -> bool:
    """A line made up only of closing brackets, commas and semicolons (e.g.
    ``)``, ``},``, ``})``) — where a preceding blank is gofmt/black-dirty."""
    stripped = line.strip()
    return bool(stripped) and stripped[0] in ")}]" and all(c in ")}],;" for c in stripped)


def _drop_blanks_before_closers(text: str) -> str:
    """Remove blank lines stranded immediately before a closing-bracket line.

    This is the only gofmt-visible artifact that section stripping introduces:
    a section ending a brace/paren group is removed but its lead-in blank
    survives, dangling before the close. Separator blanks before *surviving*
    content are intentionally left alone — gofmt keeps those.
    """
    out: list[str] = []
    for line in text.splitlines(keepends=True):
        if _is_closing_bracket_line(line):
            while out and not out[-1].strip():
                out.pop()
        out.append(line)
    return "".join(out)


# ── User-managed region splicing ──────────────────────────────────────
#
# Managed dependency files carry a ``user-managed`` region whose contents are
# preserved across re-bootstrap. Unlike lang/feature/exclude markers — which
# filter_sections consumes at render time — these markers survive into the
# generated file and are consumed here, at splice time. The two systems never
# collide because they are read at different moments, not because of where they
# sit (they can even interleave in one list; see java_segment.MODULE.bazel).
#
# The marker accepts ``#`` / ``//`` comment prefixes and also a Markdown
# HTML-comment form (``<!-- --- BEGIN user-managed --- -->``) so the region can
# live in a generated README without rendering as a heading. The closing
# ``-->`` is optional, so the ``#`` / ``//`` forms match unchanged.

_USER_BEGIN_RE = re.compile(r"^\s*(?:#|//|<!--)\s*---\s*BEGIN\s+user-managed\s*---\s*(?:-->)?\s*$")
_USER_END_RE = re.compile(r"^\s*(?:#|//|<!--)\s*---\s*END\s+user-managed\s*---\s*(?:-->)?\s*$")


def extract_user_region(content: str) -> str | None:
    """Return the text between the user-managed BEGIN/END markers (the markers
    themselves excluded), or ``None`` when a single well-formed region is not
    present.

    ``None`` means "not a managed file / nothing to preserve" — callers
    overwrite. Ambiguous shapes (a marker missing its partner, duplicate
    markers) deliberately return ``None`` rather than guess, so a malformed
    target is overwritten — and surfaced under ``--review`` — instead of being
    silently mis-spliced.
    """
    lines = content.splitlines(keepends=True)
    begin_idx: int | None = None
    end_idx: int | None = None
    for i, line in enumerate(lines):
        if _USER_BEGIN_RE.match(line):
            if begin_idx is not None:
                return None  # a second BEGIN — ambiguous
            begin_idx = i
        elif _USER_END_RE.match(line):
            if begin_idx is None or end_idx is not None:
                return None  # END before BEGIN, or a second END
            end_idx = i
    if begin_idx is None or end_idx is None:
        return None
    return "".join(lines[begin_idx + 1 : end_idx])


def has_user_region(content: str) -> bool:
    """True when *content* holds exactly one well-formed user-managed region."""
    return extract_user_region(content) is not None


def splice_user_region(rendered: str, existing: str) -> str:
    """Return *rendered* with its user-managed body replaced by *existing*'s.

    The BEGIN/END marker lines from *rendered* are kept (freshly generated), so
    only the body between them is swapped in — this is what lets a re-bootstrap
    refresh the starter baseline while carrying the user's edits forward.
    Returns *rendered* unchanged when *existing* has no extractable user region.

    Precondition: *rendered* contains a user-managed region (callers check via
    :func:`has_user_region`), so the marker scan below always finds both ends.
    """
    user_body = extract_user_region(existing)
    if user_body is None:
        return rendered
    lines = rendered.splitlines(keepends=True)
    begin_idx = next(i for i, line in enumerate(lines) if _USER_BEGIN_RE.match(line))
    end_idx = next(i for i, line in enumerate(lines) if _USER_END_RE.match(line))
    return "".join(lines[: begin_idx + 1]) + user_body + "".join(lines[end_idx:])
