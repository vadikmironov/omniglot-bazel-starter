"""O(n²) string concatenation: every round allocates a fresh string and
copies the whole accumulator — high transient allocation rate, tiny live
heap at any instant. The f-string sidesteps CPython's in-place resize
optimisation for `acc += piece`, keeping the churn honest."""


def concat(pieces: int, piece: str) -> str:
    acc = ""
    for _ in range(pieces):
        acc = f"{acc}{piece}"
    return acc
