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
    flamelens: Path | None


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
    if pprofutils is None or inferno is None:
        raise ProfileError("hermetic spine tools missing from runfiles; run via bazel run //tools/profile")

    flamelens = rlocation("PROFILE_FLAMELENS")
    if flamelens is None and (host := shutil.which("flamelens")):
        flamelens = Path(host)
    return Tools(pprofutils=pprofutils, inferno=inferno, flamelens=flamelens)


def pprof_to_folded(tools: Tools, pb: Path, folded: Path, *, trim_jemalloc: bool = False) -> None:
    _run([str(tools.pprofutils), "folded", str(pb), str(folded)])
    if trim_jemalloc:
        folded.write_text(_trim_jemalloc_frames(folded.read_text()))


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
    for line in folded.read_text().splitlines():
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


def _run(cmd: list[str], stdout: BinaryIO | None = None) -> None:
    result = subprocess.run(cmd, check=False, stdout=stdout)
    if result.returncode != 0:
        raise ProfileError(f"{Path(cmd[0]).name} failed with exit code {result.returncode}")
