"""Steadily grows a retained, reachable-but-never-reread heap: the
live-heap signature a profiler attributes to this allocation site."""


def grow(chunks: int, chunk_bytes: int) -> list[bytes]:
    """Allocates chunks chunks of chunk_bytes each and retains them all."""
    return [bytes([i % 251]) * chunk_bytes for i in range(chunks)]


def retained_bytes(retained: list[bytes]) -> int:
    return sum(len(chunk) for chunk in retained)
