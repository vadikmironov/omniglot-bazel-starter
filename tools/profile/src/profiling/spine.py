"""The shared rendering spine: pprof protobuf -> folded stacks -> inferno SVG,
plus a text top-N summary and the flamelens TUI viewer.

The hermetic tool binaries ride the runner's runfiles; their runfiles paths
arrive via PROFILE_* environment variables set in the BUILD file.
"""

import math
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from python.runfiles import Runfiles


@dataclass(frozen=True)
class Tools:
    pb2folded: Path
    inferno: Path
    collapse_perf: Path
    flamelens: Path | None
    # C++ capture only (None unless the cpp language is scaffolded): pprof
    # symbolizes gperftools' legacy profile format against the bench binary,
    # with llvm_tools_dir supplying a hermetic llvm-symbolizer.
    pprof: Path | None
    llvm_tools_dir: Path | None
    # Java capture only (None unless the java language is scaffolded):
    # async-profiler's converter renders JFR recordings as collapsed stacks.
    jfrconv: Path | None
    # Runfiles root for launching jfrconv: its java_binary bash launcher only
    # consults $JAVA_RUNFILES for runfiles discovery, which manifest-mode
    # runfiles leave unset (see jfr_to_folded). None outside a runfiles tree.
    java_runfiles: Path | None


class ProfileError(Exception):
    """Fatal runner error, reported without a traceback."""


def resolve_tools() -> Tools:
    r = Runfiles.Create()
    if r is None:
        raise ProfileError("runfiles unavailable; run via bazel run //tools/profile")

    def rlocation(env_var: str) -> Path | None:
        rpath = os.environ.get(env_var)
        if not rpath:
            return None
        resolved = r.Rlocation(rpath)
        if resolved and Path(resolved).is_file():
            return Path(resolved)
        return None

    pb2folded = rlocation("PROFILE_PB2FOLDED")
    inferno = rlocation("PROFILE_INFERNO")
    collapse_perf = rlocation("PROFILE_COLLAPSE_PERF")
    if pb2folded is None or inferno is None or collapse_perf is None:
        # Name the culprits: a stale PROFILE_* path otherwise surfaces much
        # later as "None failed with exit code 127".
        missing = [
            name
            for name, path in (
                ("pb2folded", pb2folded),
                ("inferno", inferno),
                ("collapse_perf", collapse_perf),
            )
            if path is None
        ]
        raise ProfileError(
            f"hermetic spine tools missing from runfiles ({', '.join(missing)}); run via bazel run //tools/profile"
        )

    flamelens = rlocation("PROFILE_FLAMELENS")
    if flamelens is None and (host := shutil.which("flamelens")):
        flamelens = Path(host)
    pprof = rlocation("PROFILE_PPROF")
    symbolizer = rlocation("PROFILE_LLVM_SYMBOLIZER")
    jfrconv = rlocation("PROFILE_JFRCONV")
    # Prefer JAVA_RUNFILES (directory-mode EnvVars sets it), else the runfiles
    # root RUNFILES_DIR (manifest-mode EnvVars sets that but not JAVA_RUNFILES).
    env_vars = r.EnvVars()
    runfiles_root = env_vars.get("JAVA_RUNFILES") or env_vars.get("RUNFILES_DIR")
    return Tools(
        pb2folded=pb2folded,
        inferno=inferno,
        collapse_perf=collapse_perf,
        flamelens=flamelens,
        pprof=pprof,
        llvm_tools_dir=symbolizer.parent if symbolizer is not None else None,
        jfrconv=jfrconv,
        java_runfiles=Path(runfiles_root) if runfiles_root else None,
    )


def pprof_to_folded(
    tools: Tools,
    pb: Path,
    folded: Path,
    *,
    select: str | None = None,
    unit: str | None = None,
) -> None:
    """Fold one sample type out of a pprof profile.

    Without `select` the first value is folded, which is what CPU profiles
    want. Memory callers name the bucket explicitly, since heap profiles lead
    with an object count in both the Go and gperftools shapes.
    """
    cmd = [str(tools.pb2folded)]
    if select is not None:
        cmd += ["-select", select]
    if unit is not None:
        cmd += ["-unit", unit]
    _run([*cmd, str(pb), str(folded)])


def pprof_to_table(tools: Tools, pb: Path, table: Path) -> None:
    """Emit every sample type at once as TSV (see `bucket_table`)."""
    _run([str(tools.pb2folded), "-table", str(pb), str(table)])


def gperftools_to_pb(tools: Tools, binary: Path, raw: Path, pb: Path) -> None:
    """Symbolize gperftools' legacy profile format against the binary's ELF
    symbols (via the hermetic llvm-symbolizer) and convert it to pprof."""
    if tools.pprof is None or tools.llvm_tools_dir is None:
        raise ProfileError(
            "pprof or llvm-symbolizer missing from runfiles; C++ capture needs the cpp language scaffolded"
        )
    env = {**os.environ, "PPROF_TOOLS": str(tools.llvm_tools_dir)}
    _run(
        [str(tools.pprof), "-proto", "-output", str(pb), str(binary), str(raw)],
        env=env,
    )


def jfr_to_folded(tools: Tools, jfr: Path, folded: Path, *, mode: str) -> None:
    """JFR recording -> collapsed stacks via async-profiler's converter.

    mode "cpu" selects execution samples by runnable thread state — the
    converter's own --cpu flag matches only the STATE_DEFAULT samples its
    engine writes, never JDK Flight Recorder's. mode "alloc" selects
    allocation samples weighted by size (bytes).
    """
    if tools.jfrconv is None:
        raise ProfileError("jfrconv missing from runfiles; Java capture needs the java language scaffolded")
    # jfrconv is a bazel java_binary; its bash launcher can't self-locate its
    # runfiles when execed from our tree under manifest-mode runfiles (its $0 is
    # the real bazel-out path, no .runfiles/ ancestor). It only honors
    # $JAVA_RUNFILES, so hand it the runfiles root.
    env = {**os.environ, "JAVA_RUNFILES": str(tools.java_runfiles)} if tools.java_runfiles else None
    flags = ["--state", "runnable"] if mode == "cpu" else ["--alloc", "--total"]
    _run([str(tools.jfrconv), *flags, "-o", "collapsed", str(jfr), str(folded)], env=env)
    if not folded.is_file():
        raise ProfileError(f"jfrconv produced no output for {jfr}")


def perf_to_folded(tools: Tools, perf_data: Path, folded: Path) -> None:
    """`perf script` piped through inferno-collapse-perf."""
    perf_script = subprocess.Popen(
        ["perf", "script", "-i", str(perf_data)],
        stdout=subprocess.PIPE,
    )
    with folded.open("wb") as out:
        collapse = subprocess.run(
            [str(tools.collapse_perf)],
            stdin=perf_script.stdout,
            stdout=out,
            check=False,
        )
    if perf_script.stdout is not None:
        perf_script.stdout.close()
    if perf_script.wait() != 0:
        raise ProfileError("perf script failed to read the recording")
    if collapse.returncode != 0:
        raise ProfileError(f"inferno-collapse-perf failed with exit code {collapse.returncode}")


def folded_to_svg(tools: Tools, folded: Path, svg: Path, *, title: str, countname: str) -> None:
    with svg.open("wb") as out:
        _run(
            [str(tools.inferno), "--title", title, "--countname", countname, str(folded)],
            stdout=out,
        )


def view(tools: Tools, folded: Path) -> None:
    if tools.flamelens is None:
        raise ProfileError(
            "flamelens is not available; expected it in runfiles or on PATH (host install: cargo install flamelens)"
        )
    subprocess.run([str(tools.flamelens), str(folded)], check=False)


def top_n(folded: Path, n: int = 10) -> str:
    """Self/cumulative hot-frame summary from folded stacks."""
    self_weight: dict[str, int] = {}
    cumulative: dict[str, int] = {}
    total = 0
    for line in folded.read_text(encoding="utf-8").splitlines():
        stack, _, count_str = line.rpartition(" ")
        if not stack or not count_str.isdigit():
            continue
        count = int(count_str)
        total += count
        frames = stack.split(";")
        leaf = frames[-1]
        self_weight[leaf] = self_weight.get(leaf, 0) + count
        for frame in set(frames):
            cumulative[frame] = cumulative.get(frame, 0) + count

    if total == 0:
        return "top: (empty profile)\n"

    def table(header: str, weights: dict[str, int]) -> list[str]:
        rows = [header]
        ranked = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)[:n]
        rows += [f"  {count:>12}  {100 * count / total:5.1f}%  {frame}" for frame, count in ranked]
        return rows

    lines = table(f"top {n} by self weight:", self_weight)
    lines += table(f"top {n} by cumulative weight:", cumulative)
    return "\n".join(lines) + "\n"


# The four canonical heap buckets, in report order.
BUCKETS = ("alloc_objects", "alloc_space", "inuse_objects", "inuse_space")

# gperftools' 2-type shape appears only when nothing was freed, i.e. when the
# allocated counters equal the in-use ones — so `space`/`objects` populate both
# halves rather than being a third kind of bucket.
_ALIASES = {
    "space": ("inuse_space", "alloc_space"),
    "objects": ("inuse_objects", "alloc_objects"),
}


# How a shim measured its heap. Not every capture is an estimate over bytes,
# so this is an enum rather than a sampling rate:
#
#   exact                  every allocation tracked (tcmalloc, memray)
#   sampled_bytes:N        one sample per N bytes (Go, Rust) — supports an error bar
#   sampled_events:N       throttled to N events/sec (JFR alloc): weights are
#                          honest, object counts are not
#   attribution_only       shows *where* memory came from but not how much
#                          (JFR's bounded old-object queue) — ratios suppressed
PRECISION_EXACT = "exact"
PRECISION_SAMPLED_BYTES = "sampled_bytes"
PRECISION_SAMPLED_EVENTS = "sampled_events"
PRECISION_ATTRIBUTION_ONLY = "attribution_only"


@dataclass(frozen=True)
class Meta:
    """Footprint and precision recorded by a workload's shim, if it wrote any."""

    vmrss_bytes: int | None = None
    vmhwm_bytes: int | None = None
    # Whole-heap live bytes, where the runtime can state them exactly but
    # cannot attribute them to call sites (Java). Process-scoped: it includes
    # runtime and profiler overhead, so it is a footprint figure only — never a
    # substitute for the inuse_space bucket in a per-frame ratio.
    heap_live_bytes: int | None = None
    # "exact", "sampled_bytes:32768", "sampled_events:300", "attribution_only".
    precision: str | None = None

    @property
    def kind(self) -> str | None:
        return self.precision.partition(":")[0] if self.precision else None

    @property
    def sample_rate_bytes(self) -> int | None:
        """Mean bytes between samples, for `sampled_bytes` captures only."""
        precision = self.precision
        if precision is None or self.kind != PRECISION_SAMPLED_BYTES:
            return None
        try:
            return int(precision.partition(":")[2])
        except ValueError:
            return None

    @property
    def totals_are_meaningful(self) -> bool:
        """False when the capture attributes memory without measuring it, so
        summing it into a ratio would invent a number."""
        return self.kind != PRECISION_ATTRIBUTION_ONLY


@dataclass(frozen=True)
class BucketTable:
    """Per-stack values for every sample type a profile carries."""

    types: list[str]
    rows: list[tuple[str, list[int]]]

    def column(self, bucket: str) -> int | None:
        for i, name in enumerate(self.types):
            if name == bucket:
                return i
            for alias, targets in _ALIASES.items():
                if name == alias and bucket in targets:
                    return i
        return None


def read_meta(path: Path) -> Meta | None:
    if not path.is_file():
        return None
    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep:
            fields[key.strip()] = value.strip()

    def number(key: str) -> int | None:
        try:
            return int(fields[key])
        except (KeyError, ValueError):
            return None

    precision = fields.get("precision")
    if precision is None and (legacy := number("sample_rate_bytes")) is not None:
        # Pre-enum shims wrote a bare byte rate, with 0 meaning exact.
        precision = f"{PRECISION_SAMPLED_BYTES}:{legacy}" if legacy else PRECISION_EXACT
    return Meta(
        vmrss_bytes=number("vmrss_bytes"),
        vmhwm_bytes=number("vmhwm_bytes"),
        heap_live_bytes=number("heap_live_bytes"),
        precision=precision,
    )


def folded_to_table(sources: dict[str, Path]) -> BucketTable:
    """Join per-bucket folded files into the table `bucket_report` consumes.

    Languages whose capture never reaches pprof — Java's JFR, Python's memray —
    can still emit folded stacks, one file per bucket they can measure. Merging
    them here means they share the whole report path instead of needing their
    own renderer.
    """
    types = [bucket for bucket in BUCKETS if bucket in sources]
    merged: dict[str, list[int]] = {}
    for index, bucket in enumerate(types):
        for line in sources[bucket].read_text(encoding="utf-8").splitlines():
            stack, _, count = line.rpartition(" ")
            if not stack or not count.isdigit():
                continue
            row = merged.setdefault(stack, [0] * len(types))
            row[index] += int(count)
    return BucketTable(types=types, rows=list(merged.items()))


def bucket_table(path: Path) -> BucketTable:
    types: list[str] = []
    merged: dict[str, list[int]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#stack"):
            # Header cells are "<type>/<unit>"; the unit is implied by the name.
            types = [cell.partition("/")[0] for cell in line.split("\t")[1:]]
            continue
        cells = line.split("\t")
        if len(cells) < 2:
            continue
        try:
            values = [int(cell) for cell in cells[1:]]
        except ValueError:
            continue
        stack = cells[0]
        if not stack:
            continue
        if previous := merged.get(stack):
            merged[stack] = [a + b for a, b in zip(previous, values, strict=False)]
        else:
            merged[stack] = values
    return BucketTable(types=types, rows=list(merged.items()))


def bucket_report(table: BucketTable, meta: Meta | None = None, n: int = 10) -> str:
    """Four-bucket self-weight table plus the derived ratios.

    Each bucket answers a different question — allocation *count* drives
    allocator CPU, allocation *bytes* drive GC pacing, live bytes drive
    footprint, live *count* drives mark cost — and the ratios between them are
    what separate a churn problem from a retention or fragmentation one.
    """
    cols = {bucket: table.column(bucket) for bucket in BUCKETS}
    if all(idx is None for idx in cols.values()):
        return ""

    totals: dict[str, int] = dict.fromkeys(BUCKETS, 0)
    self_weight: dict[str, dict[str, int]] = {bucket: {} for bucket in BUCKETS}
    for stack, values in table.rows:
        leaf = stack.rpartition(";")[2]
        for bucket, idx in cols.items():
            if idx is None or idx >= len(values):
                continue
            value = values[idx]
            if value <= 0:
                continue
            totals[bucket] += value
            self_weight[bucket][leaf] = self_weight[bucket].get(leaf, 0) + value

    rank_by = "inuse_space" if cols["inuse_space"] is not None else "alloc_space"
    ranked = sorted(self_weight[rank_by].items(), key=lambda kv: kv[1], reverse=True)[:n]

    lines = [f"buckets (self weight, top {n} by {rank_by}):"]
    lines.append("  " + "".join(f"{bucket:>16}" for bucket in BUCKETS) + "  frame")
    for leaf, _ in ranked:
        cells = "".join(f"{_cell(self_weight[b].get(leaf), cols[b]):>16}" for b in BUCKETS)
        lines.append(f"  {cells}  {leaf}")
    lines.append("  " + "".join(f"{_cell(totals[b], cols[b]):>16}" for b in BUCKETS) + "  TOTAL")
    lines.append("")
    lines += _ratio_lines(totals, cols, meta)
    return "\n".join(lines) + "\n"


def _cell(value: int | None, column: int | None) -> str:
    if column is None:
        # Distinguish "this language cannot measure it" from a measured zero.
        return "—"
    return str(value or 0)


def _ratio_lines(totals: dict[str, int], cols: dict[str, int | None], meta: Meta | None) -> list[str]:
    rate = meta.sample_rate_bytes if meta else None
    live = totals["inuse_space"]
    # A sampled live heap is an estimate over roughly inuse_space/rate draws,
    # so its relative error is ~1/sqrt(n). Reporting that beats a pass/fail
    # gate: 2,000 samples of 1 KiB objects is accurate to ~2% even though no
    # individual object is likely to be sampled, while a handful of draws is
    # noise however large the extrapolated total looks.
    effective = live / rate if rate else None

    def ratio(label: str, formula: str, value: str) -> str:
        return f"  {label:<12} {formula:<34} {value}"

    # An attribution-only capture (JFR's bounded old-object queue) knows where
    # memory came from but not how much, so every ratio over it would be
    # invented. Suppress rather than print a confident wrong number.
    measured = meta.totals_are_meaningful if meta else True

    def have(*buckets: str) -> bool:
        # A bucket the language cannot capture reads "—"; never compute a
        # ratio against an absent column's implicit zero.
        return measured and all(cols[bucket] is not None for bucket in buckets)

    turnover = _times(totals["alloc_space"], live) if have("alloc_space", "inuse_space") else "—"
    mean_alloc = _mean(totals["alloc_space"], totals["alloc_objects"]) if have("alloc_space", "alloc_objects") else "—"
    mean_live = _mean(live, totals["inuse_objects"]) if have("inuse_space", "inuse_objects") else "—"
    freed = str(totals["alloc_objects"] - totals["inuse_objects"]) if have("alloc_objects", "inuse_objects") else "—"

    lines = ["ratios:"]
    lines.append(ratio("turnover", "(alloc_space / inuse_space)", turnover))
    lines.append(ratio("mean alloc", "(alloc_space / alloc_objects)", mean_alloc))
    lines.append(ratio("mean live", "(inuse_space / inuse_objects)", mean_live))
    lines.append(ratio("freed", "(alloc_objects - inuse_objects)", freed))
    rss = meta.vmrss_bytes if meta else None
    if have("inuse_space"):
        lines.append(ratio("live / RSS", "(inuse_space / VmRSS)", _percent(live, rss)))
    elif meta and meta.heap_live_bytes:
        # No per-frame live bucket, but the runtime states its live heap exactly.
        # Label the different source: this covers runtime overhead too, so it is
        # not comparable with the attributed columns above.
        lines.append(ratio("live / RSS", "(heap live / VmRSS)", _percent(meta.heap_live_bytes, rss)))
        lines.append(ratio("heap live", "(whole heap, not attributed)", _bytes(meta.heap_live_bytes)))
    else:
        lines.append(ratio("live / RSS", "(inuse_space / VmRSS)", "—"))
    if meta and meta.vmhwm_bytes:
        lines.append(ratio("peak RSS", "(VmHWM)", _bytes(meta.vmhwm_bytes)))
    lines += _precision_lines(meta, effective, rate)
    return lines


def _precision_lines(meta: Meta | None, effective: float | None, rate: int | None) -> list[str]:
    def ratio(label: str, formula: str, value: str) -> str:
        return f"  {label:<12} {formula:<34} {value}"

    if meta is None or meta.kind is None:
        return []
    if meta.kind == PRECISION_EXACT:
        return [ratio("precision", "(every allocation tracked)", "exact")]
    if meta.kind == PRECISION_ATTRIBUTION_ONLY:
        return [
            ratio("precision", "(attribution only)", "sampled call sites, not a heap census"),
            "  ! this capture shows where memory came from, not how much; totals and ratios are withheld",
        ]
    if meta.kind == PRECISION_SAMPLED_EVENTS:
        events = meta.precision.partition(":")[2] if meta.precision else ""
        return [
            ratio("precision", f"(throttled @ {events} events/s)", "byte weights are estimates, counts unavailable"),
            "  ! throttled sampling undercounts high allocation rates; read the attribution as relative, not absolute",
        ]
    if effective is not None and rate:
        error = f"±{100 / math.sqrt(effective):.0f}%" if effective > 0 else "unbounded"
        lines = [ratio("precision", f"(sampled @ {_bytes(rate)})", f"~{effective:.0f} live samples, {error}")]
        if effective < 10:
            lines.append("  ! too few live samples to trust inuse_* or any ratio derived from it")
        return lines
    return []


def _times(numerator: int, denominator: int) -> str:
    if not denominator:
        return "—"
    return f"{numerator / denominator:,.2f}x"


def _mean(space: int, objects: int) -> str:
    if not objects:
        return "—"
    return _bytes(round(space / objects))


def _percent(part: int, whole: int | None) -> str:
    if not whole:
        return "—"
    return f"{100 * part / whole:.1f}%"


def _bytes(value: int | None) -> str:
    if value is None:
        return "—"
    if value < 1024:
        return f"{value} B"
    for suffix, scale in (("KiB", 1024), ("MiB", 1024**2), ("GiB", 1024**3)):
        if value < scale * 1024:
            return f"{value:,} B ({value / scale:.1f} {suffix})"
    return f"{value:,} B"


def _run(cmd: list[str], stdout: BinaryIO | None = None, env: dict[str, str] | None = None) -> None:
    result = subprocess.run(cmd, check=False, stdout=stdout, env=env)
    if result.returncode != 0:
        raise ProfileError(f"{Path(cmd[0]).name} failed with exit code {result.returncode}")
