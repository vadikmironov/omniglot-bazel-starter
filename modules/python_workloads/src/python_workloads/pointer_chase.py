"""Pointer chasing over a single-cycle permutation versus a contiguous
sum of the same buffer: dependent random loads against streaming loads."""

import random


def build_cycle(n: int, seed: int) -> list[int]:
    """Single-cycle permutation of 0..n (Sattolo's algorithm): following
    i = perm[i] from any start visits every slot exactly once."""
    rng = random.Random(seed)
    perm = list(range(n))
    for i in range(n - 1, 0, -1):
        j = rng.randrange(i)
        perm[i], perm[j] = perm[j], perm[i]
    return perm


def chase_sum(perm: list[int]) -> int:
    """Walks the cycle once from slot 0, summing the visited indices."""
    idx = 0
    acc = 0
    for _ in perm:
        acc += idx
        idx = perm[idx]
    return acc


def array_sum(perm: list[int]) -> int:
    """The streaming counterpart: a contiguous sum of the buffer."""
    return sum(perm)
