"""In-place recursive quicksort over seeded random input; the recursion
gives the flamegraph its quicksort → partition tower."""

import random


def random_slice(n: int, seed: int) -> list[int]:
    rng = random.Random(seed)
    return [rng.getrandbits(64) for _ in range(n)]


def quicksort(v: list[int]) -> None:
    _quicksort(v, 0, len(v))


def _quicksort(v: list[int], lo: int, hi: int) -> None:
    if hi - lo <= 1:
        return
    mid = _partition(v, lo, hi)
    _quicksort(v, lo, mid)
    _quicksort(v, mid + 1, hi)


def _partition(v: list[int], lo: int, hi: int) -> int:
    """Lomuto partition around the last element; returns the pivot's final slot."""
    pivot = v[hi - 1]
    store = lo
    for i in range(lo, hi - 1):
        if v[i] <= pivot:
            v[store], v[i] = v[i], v[store]
            store += 1
    v[store], v[hi - 1] = v[hi - 1], v[store]
    return store
