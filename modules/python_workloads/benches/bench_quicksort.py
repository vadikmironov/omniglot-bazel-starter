"""Quicksort bench: recursive call tree renders as a quicksort →
partition flamegraph tower, with a branch-miss story on random input."""

from python_workloads.quicksort import quicksort, random_slice
from python_workloads.workload_n import workload_n

QUICKSORT_DEFAULT_N = 100_000


def test_quicksort(benchmark):
    input_slice = random_slice(workload_n(QUICKSORT_DEFAULT_N), 42)

    def run():
        buf = input_slice.copy()
        quicksort(buf)
        return buf

    benchmark(run)
