"""Dense n×n matrix multiply in two loop orders: ijk strides column-wise
through b (cache-hostile), ikj streams both operands row-major."""

import random


def random_matrix(n: int, seed: int) -> list[float]:
    """Row-major n×n matrix filled from a seeded PRNG."""
    rng = random.Random(seed)
    return [rng.random() for _ in range(n * n)]


def multiply_ijk(a: list[float], b: list[float], n: int) -> list[float]:
    c = [0.0] * (n * n)
    for i in range(n):
        for j in range(n):
            acc = 0.0
            for k in range(n):
                acc += a[i * n + k] * b[k * n + j]
            c[i * n + j] = acc
    return c


def multiply_ikj(a: list[float], b: list[float], n: int) -> list[float]:
    c = [0.0] * (n * n)
    for i in range(n):
        for k in range(n):
            aik = a[i * n + k]
            row = k * n
            for j in range(n):
                c[i * n + j] += aik * b[row + j]
    return c
