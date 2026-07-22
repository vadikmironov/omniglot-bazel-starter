"""The shared rendering spine: pprof protobuf -> folded stacks -> inferno SVG,
plus a text top-N summary and the flamelens TUI viewer.

The hermetic tool binaries ride the runner's runfiles; their runfiles paths
arrive via PROFILE_* environment variables set in the BUILD file.
"""

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from python.runfiles import Runfiles


@dataclass(frozen=True)
class Tools:
    pprofutils: Path
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

    pprofutils = rlocation("PROFILE_PPROFUTILS")
    inferno = rlocation("PROFILE_INFERNO")
    collapse_perf = rlocation("PROFILE_COLLAPSE_PERF")
    if pprofutils is None or inferno is None or collapse_perf is None:
        raise ProfileError("hermetic spine tools missing from runfiles; run via bazel run //tools/profile")

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
        pprofutils=pprofutils,
        inferno=inferno,
        collapse_perf=collapse_perf,
        flamelens=flamelens,
        pprof=pprof,
        llvm_tools_dir=symbolizer.parent if symbolizer is not None else None,
        jfrconv=jfrconv,
        java_runfiles=Path(runfiles_root) if runfiles_root else None,
    )


def pprof_to_folded(tools: Tools, pb: Path, folded: Path, *, trim_jemalloc: bool = False) -> None:
    _run([str(tools.pprofutils), "folded", str(pb), str(folded)])
    if trim_jemalloc:
        folded.write_text(_trim_jemalloc_frames(folded.read_text(encoding="utf-8")), encoding="utf-8")


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


def _trim_jemalloc_frames(text: str) -> str:
    """Drop jemalloc's own profiling frames from the stack tails and merge the
    stacks this collapses together."""
    merged: dict[str, int] = {}
    for line in text.splitlines():
        stack, _, count_str = line.rpartition(" ")
        if not stack or not count_str.isdigit():
            continue
        frames = stack.split(";")
        while frames and (frames[-1].startswith("_rjem_je_") or frames[-1] == "prof_backtrace_impl"):
            frames.pop()
        if not frames:
            continue
        key = ";".join(frames)
        merged[key] = merged.get(key, 0) + int(count_str)
    return "".join(f"{stack} {count}\n" for stack, count in merged.items())


def _run(cmd: list[str], stdout: BinaryIO | None = None, env: dict[str, str] | None = None) -> None:
    result = subprocess.run(cmd, check=False, stdout=stdout, env=env)
    if result.returncode != 0:
        raise ProfileError(f"{Path(cmd[0]).name} failed with exit code {result.returncode}")
