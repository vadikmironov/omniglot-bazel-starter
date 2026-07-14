"""Shared shim for the one-shot memory workloads: the workload runs under
memray's tracker, and the allocations still live when tracking stopped are
written to $MEMPROF_OUT as folded stacks (bytes) for the //tools/profile
spine. Without MEMPROF_OUT the workload runs untracked."""

import os
from pathlib import Path


def run_profiled(workload):
    """Run workload() and write its live-heap folded profile.

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
    _write_folded(capture, Path(out))
    capture.unlink()
    return result, out


def _write_folded(capture: Path, out: Path) -> None:
    from memray import FileReader

    reader = FileReader(capture)
    stacks: dict[str, int] = {}
    for record in reader.get_leaked_allocation_records(merge_threads=True):
        frames = record.stack_trace()
        stack = ";".join(func for func, _file, _line in reversed(frames)) or "[unknown]"
        stacks[stack] = stacks.get(stack, 0) + record.size
    with out.open("w", encoding="utf-8") as fh:
        for stack, size in stacks.items():
            fh.write(f"{stack} {size}\n")
