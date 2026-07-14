"""Matrix-multiply bench: the ijk vs ikj loop-order gap is cache
behaviour — in-process profiles show a hot loop, an external
sampler's cache counters explain the difference."""

from python_workloads.matmul import multiply_ijk, multiply_ikj, random_matrix
from python_workloads.workload_n import workload_n

MATMUL_DEFAULT_N = 64


def test_matmul_ijk(benchmark):
    n = workload_n(MATMUL_DEFAULT_N)
    a = random_matrix(n, 42)
    b = random_matrix(n, 43)
    benchmark(multiply_ijk, a, b, n)


def test_matmul_ikj(benchmark):
    n = workload_n(MATMUL_DEFAULT_N)
    a = random_matrix(n, 42)
    b = random_matrix(n, 43)
    benchmark(multiply_ikj, a, b, n)
