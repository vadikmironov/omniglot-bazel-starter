"""Shared shim for the one-shot memory workloads: the workload runs under
memray's tracker and its allocations are written as folded stacks next to
$MEMPROF_OUT for the //tools/profile spine.

memray records every allocation rather than sampling, so both halves of the
picture are available exactly: all allocations (cumulative churn) and those
still live when tracking stopped (retained heap). Each bucket goes to its own
folded file, which the runner joins into one report; $MEMPROF_OUT itself holds
the live bytes, the view the flamegraph renders. Without MEMPROF_OUT the
workload runs untracked."""

import os
from pathlib import Path

# Suffixes appended to $MEMPROF_OUT, one per bucket. The names must match
# tools/profile/src/profiling/spine.py's BUCKETS — the runner joins by them.
BUCKET_SUFFIXES = {
    "alloc_objects": ".alloc_objects.folded",
    "alloc_space": ".alloc_space.folded",
    "inuse_objects": ".inuse_objects.folded",
    "inuse_space": ".inuse_space.folded",
}


def run_profiled(workload):
    """Run workload() and write its memory profile.

    Returns (workload result, profile path or None). The result is kept
    alive across the tracker shutdown so its allocations register as the
    live heap.
    """
    out = os.environ.get("MEMPROF_OUT")
    if out is None:
        return workload(), None

    import memray

    capture = Path(out + ".bin")
    capture.unlink(missing_ok=True)
    with memray.Tracker(capture):
        result = workload()
    _write_profile(capture, Path(out))
    capture.unlink()
    return result, out


def _write_profile(capture: Path, out: Path) -> None:
    from memray import FileReader

    reader = FileReader(capture)
    # Each generator is single-use, so read the two record sets separately.
    # get_allocation_records takes no merge_threads — it yields raw per-thread
    # allocations, which folding by stack string merges anyway.
    _write_buckets(reader.get_allocation_records(), out, "alloc")
    _write_buckets(reader.get_leaked_allocation_records(merge_threads=True), out, "inuse")
    _write_meta(out)
    live = out.with_name(out.name + BUCKET_SUFFIXES["inuse_space"])
    out.write_text(live.read_text(encoding="utf-8"), encoding="utf-8")


def _write_buckets(records, out: Path, half: str) -> None:
    """Fold one record set into its bytes and its count bucket."""
    from memray import AllocatorType

    # get_allocation_records() replays frees as well as allocations, and asking
    # a deallocation for its stack raises — only allocations carry one.
    deallocators = {AllocatorType.PYMALLOC_FREE, AllocatorType.FREE, AllocatorType.MUNMAP}
    space: dict[str, int] = {}
    objects: dict[str, int] = {}
    for record in records:
        if record.allocator in deallocators:
            continue
        frames = record.stack_trace()
        stack = ";".join(func for func, _file, _line in reversed(frames)) or "[unknown]"
        space[stack] = space.get(stack, 0) + record.size
        # Records are per-allocation unless memray aggregated them, in which
        # case n_allocations carries how many this row stands for.
        objects[stack] = objects.get(stack, 0) + getattr(record, "n_allocations", 1)
    _write_folded(out, f"{half}_space", space)
    _write_folded(out, f"{half}_objects", objects)


def _write_folded(out: Path, bucket: str, stacks: dict[str, int]) -> None:
    path = out.with_name(out.name + BUCKET_SUFFIXES[bucket])
    with path.open("w", encoding="utf-8") as fh:
        for stack, value in stacks.items():
            if value > 0:
                fh.write(f"{stack} {value}\n")


def _write_meta(out: Path) -> None:
    """Footprint and precision for the runner's ratio block: live bytes over
    VmRSS is the only signal separating fragmentation from real retention."""
    current, peak = _read_rss()
    path = out.with_name(out.name + ".meta")
    path.write_text(f"vmrss_bytes={current}\nvmhwm_bytes={peak}\nprecision=exact\n", encoding="utf-8")


def _read_rss() -> tuple[int, int]:
    """Current and peak RSS in bytes, or zeroes where /proc is unavailable."""
    try:
        status = Path("/proc/self/status").read_text(encoding="utf-8")
    except OSError:
        return 0, 0
    fields = {"VmRSS": 0, "VmHWM": 0}
    for line in status.splitlines():
        name, _, value = line.partition(":")
        if name in fields:
            fields[name] = int(value.strip().removesuffix(" kB")) * 1024
    return fields["VmRSS"], fields["VmHWM"]
