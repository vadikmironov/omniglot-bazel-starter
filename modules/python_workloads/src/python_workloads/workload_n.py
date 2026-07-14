"""Workload sizing shared by the bench and memory targets."""

import os


def workload_n(fallback: int) -> int:
    """Workload size from WORKLOAD_N, falling back to the target's default."""
    raw = os.environ.get("WORKLOAD_N")
    if raw is None:
        return fallback
    try:
        return int(raw)
    except ValueError:
        return fallback
