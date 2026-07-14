"""Pointer-chase bench: serially dependent random loads (memory-latency
bound) against a contiguous sum of the same buffer (bandwidth bound)."""

from python_workloads.pointer_chase import array_sum, build_cycle, chase_sum
from python_workloads.workload_n import workload_n

CHASE_DEFAULT_N = 1 << 20


def test_chase(benchmark):
    perm = build_cycle(workload_n(CHASE_DEFAULT_N), 42)
    benchmark(chase_sum, perm)


def test_array_sum(benchmark):
    perm = build_cycle(workload_n(CHASE_DEFAULT_N), 42)
    benchmark(array_sum, perm)
