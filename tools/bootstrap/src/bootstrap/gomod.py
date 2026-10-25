"""Carrying a repo's Go dependencies across re-bootstrap.

A Go dependency lives in three files: its requirement in ``go.mod``, its
checksums in ``go.sum`` and its repository name in the ``use_repo(go_deps, …)``
call of the Go MODULE segment. None of them can hold a user-managed region:
``go get``, ``go mod tidy`` and ``bazel mod tidy`` rewrite them, sorting lines
with their comments attached, so a marker would not stay put. A re-bootstrap
used to replace all three, dropping every dependency the repo had added. The
lock refresh could not bring them back either: its ``go mod tidy`` re-resolves
a missing import at its latest version, and rules_go runs ``bazel mod tidy``
only when ``go.mod`` or ``go.sum`` changed.

So these files are merged instead. The starter's rendered file is the base, and
the repo's entries are folded into it, the way Go's minimal version selection
combines requirements:

* ``require`` — the higher version where both require a module; it stays
  direct if either side imports it directly.
* ``go`` / ``toolchain`` — the higher version.
* ``module`` — the repo's path, which may have been set to a real import path.
* An entry the starter could never ship (under any language or feature
  selection) is the repo's, so it is added. One the starter could ship but
  this selection does not is left out, so deselecting a feature still drops
  its modules.
* ``go.sum`` — the union of both files. A checksum nothing needs any more is
  harmless, and the next ``go mod tidy`` drops it.

Comments outside the starter's own lines are not carried over.
"""

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

# ── Version order ──────────────────────────────────────────────────────

_SEMVER = re.compile(r"v(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?")
_GOVER = re.compile(r"(?:go)?(\d+)\.(\d+)(?:\.(\d+)|(alpha|beta|rc)(\d+))?")
_GOVER_STAGES = {"alpha": 1, "beta": 2, "rc": 3}


def semver_key(version: str) -> tuple | None:
    """Sort key for a module version, in golang.org/x/mod/semver order.

    Pseudo-versions are prereleases by construction, so they order correctly
    too. Build metadata (``+incompatible``) does not affect the order. None
    when *version* is not a semantic version.
    """
    m = _SEMVER.fullmatch(version)
    if not m:
        return None
    major, minor, patch, pre = m.groups()
    release = (int(major), int(minor or 0), int(patch or 0))
    if pre is None:
        return (*release, (1,))  # a release outranks every prerelease of it
    # Numeric identifiers compare as numbers and rank below alphanumeric ones;
    # a shorter list of equal identifiers ranks lower.
    ids = tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in pre.split("."))
    return (*release, (0, ids))


def gover_key(version: str) -> tuple[int, ...] | None:
    """Sort key for a ``go`` or ``toolchain`` version: 1.21 < 1.21rc1 < 1.21.0.

    A toolchain's ``go`` prefix and ``-suffix`` are ignored. None when
    *version* is not a Go version.
    """
    m = _GOVER.fullmatch(version.split("-", 1)[0])
    if not m:
        return None
    major, minor, patch, stage, n = m.groups()
    if patch is not None:
        return (int(major), int(minor), 4, int(patch))
    if stage is not None:
        return (int(major), int(minor), _GOVER_STAGES[stage], int(n))
    return (int(major), int(minor), 0, 0)  # a language version, below its releases


def _higher(theirs: str, ours: str, key: Callable[[str], tuple | None]) -> bool:
    a, b = key(theirs), key(ours)
    return a is not None and b is not None and a > b


# ── go.mod ─────────────────────────────────────────────────────────────

_BLOCK_START = re.compile(r"(\w+)\s*\(")
# Directives that take one line each, never a block.
_SINGLE = ("module", "go", "toolchain")
# Where an added directive goes, in go mod tidy's usual order.
_ORDER = ("module", "go", "toolchain", "godebug", "require", "tool", "ignore", "exclude", "replace", "retract")


@dataclass(frozen=True)
class _Entry:
    """One go.mod entry: a directive line, or one line of a directive block."""

    verb: str
    args: tuple[str, ...]
    comment: str  # text after "//", stripped
    line: int  # index into text.split("\n")
    in_block: bool

    @property
    def key(self) -> tuple[str, ...]:
        """What makes two entries the same entry, versions aside."""
        if self.verb in _SINGLE:
            return (self.verb,)
        if self.verb == "require" and self.args:
            return (self.verb, self.args[0])
        if self.verb == "replace" and "=>" in self.args:
            return (self.verb, *self.args[: self.args.index("=>")])
        if self.verb == "godebug":
            return (self.verb, " ".join(self.args).split("=", 1)[0].strip())
        return (self.verb, *self.args)

    @property
    def indirect(self) -> bool:
        # cmd/go's own test: the comment is "indirect", or starts "indirect;".
        return self.comment == "indirect" or self.comment.startswith("indirect;")


def _parse_go_mod(text: str) -> list[_Entry]:
    entries: list[_Entry] = []
    block: str | None = None
    for i, raw in enumerate(text.split("\n")):
        body, _, comment = raw.partition("//")
        body, comment = body.strip(), comment.strip()
        if not body:
            continue
        if block is not None:
            if body == ")":
                block = None
            else:
                entries.append(_Entry(block, _args(body), comment, i, True))
            continue
        start = _BLOCK_START.fullmatch(body)
        if start:
            block = start.group(1)
            continue
        verb, *rest = body.split(None, 1)
        entries.append(_Entry(verb, _args(rest[0] if rest else ""), comment, i, False))
    return entries


def _args(body: str) -> tuple[str, ...]:
    return tuple(arg.strip('"') for arg in body.split())


def _format(verb: str | None, args: Iterable[str], comment: str) -> str:
    text = " ".join(args) if verb is None else " ".join((verb, *args))
    return f"{text} // {comment}" if comment else text


def _fold(ours: _Entry, theirs: _Entry) -> tuple[tuple[str, ...], str]:
    """The args and comment for an entry both files carry."""
    if ours.verb == "module":
        return theirs.args, ours.comment
    if ours.verb in ("go", "toolchain") and ours.args and theirs.args:
        newer = _higher(theirs.args[0], ours.args[0], gover_key)
        return (theirs.args if newer else ours.args), ours.comment
    if ours.verb == "require" and len(ours.args) > 1 and len(theirs.args) > 1:
        args = theirs.args if _higher(theirs.args[1], ours.args[1], semver_key) else ours.args
        # Direct if either side imports it directly.
        comment = "" if ours.indirect and not theirs.indirect else ours.comment
        return args, comment
    return ours.args, ours.comment


def _section(verb: str, entries: list[_Entry]) -> str:
    entries = sorted(entries, key=lambda e: e.key)
    if verb in _SINGLE or len(entries) == 1:
        return "".join(f"{_format(verb, e.args, e.comment)}\n" for e in entries)
    return f"{verb} (\n" + "".join(f"\t{_format(None, e.args, e.comment)}\n" for e in entries) + ")\n"


def merge_go_mod(rendered: str, existing: str, shippable: str) -> str:
    """*rendered* (the starter's go.mod) with the repo's *existing* one folded in.

    *shippable* is the starter's go.mod rendered with every language and
    feature selected: an entry of the repo's that it lacks is the repo's own.
    """
    lines = rendered.split("\n")
    ours = {e.key: e for e in _parse_go_mod(rendered)}
    starters = {e.key for e in _parse_go_mod(shippable)}
    added: dict[str, dict[tuple[str, ...], _Entry]] = {}
    for theirs in _parse_go_mod(existing):
        mine = ours.get(theirs.key)
        if mine is None:
            if theirs.key not in starters:
                added.setdefault(theirs.verb, {})[theirs.key] = theirs
            continue
        args, comment = _fold(mine, theirs)
        if (args, comment) != (mine.args, mine.comment):
            raw = lines[mine.line]
            indent = raw[: len(raw) - len(raw.lstrip())]
            lines[mine.line] = indent + _format(None if mine.in_block else mine.verb, args, comment)
    text = "\n".join(lines)
    if not added:
        return text
    order = {verb: i for i, verb in enumerate(_ORDER)}
    verbs = sorted(added, key=lambda v: (order.get(v, len(order)), v))
    return text.rstrip("\n") + "\n" + "".join(f"\n{_section(v, list(added[v].values()))}" for v in verbs)


# ── go.sum ─────────────────────────────────────────────────────────────


def _sum_order(line: str) -> tuple:
    # cmd/go writes go.sum sorted by module path, then version, with a
    # version's /go.mod hash after its module hash.
    path, version = (line.split() + ["", ""])[:2]
    version, _, go_mod = version.partition("/")
    return (path, semver_key(version) or (), go_mod, line)


def merge_go_sum(rendered: str, existing: str, _shippable: str = "") -> str:
    """The union of the starter's and the repo's go.sum, in the order Go writes it.

    Takes *_shippable* only to match the other mergers: a checksum nothing
    needs is harmless, so every line of both files stays.
    """
    lines = {line.strip() for line in (*rendered.splitlines(), *existing.splitlines()) if line.strip()}
    return "".join(f"{line}\n" for line in sorted(lines, key=_sum_order))


# ── use_repo(go_deps, …) ───────────────────────────────────────────────

_USE_REPO = re.compile(r"use_repo\(\s*go_deps\s*(?:,(?P<names>[^)]*))?\)")
_REPO_NAME = re.compile(r'"([^"]+)"')


def _repo_names(text: str) -> set[str]:
    return {name for m in _USE_REPO.finditer(text) for name in _REPO_NAME.findall(m.group("names") or "")}


def merge_go_use_repo(rendered: str, existing: str, shippable: str) -> str:
    """*rendered* (the starter's Go MODULE segment) with the repo's go_deps repos added.

    The repo's ``use_repo(go_deps, …)`` names that *shippable* (the segment
    rendered with every language and feature) lacks are added to the first
    such call, where ``bazel mod tidy`` keeps them.
    """
    extra = sorted(_repo_names(existing) - _repo_names(shippable) - _repo_names(rendered))
    first = _USE_REPO.search(rendered)
    if not extra or first is None:
        return rendered
    call = first.group(0)
    if "\n" in call:
        body = call[: call.rindex(")")].rstrip()
        last = body.rsplit("\n", 1)[-1]
        indent = last[: len(last) - len(last.lstrip())] or "    "
        merged = body.rstrip(",") + ",\n" + "".join(f'{indent}"{name}",\n' for name in extra) + ")"
    else:
        merged = call[:-1] + "".join(f', "{name}"' for name in extra) + ")"
    return rendered[: first.start()] + merged + rendered[first.end() :]
