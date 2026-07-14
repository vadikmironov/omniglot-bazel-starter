"""One-shot retained-growth workload: the heap profile attributes the
whole live heap to the growth site."""

from prof_dump import run_profiled
from python_workloads.retained_growth import grow, retained_bytes
from python_workloads.workload_n import workload_n

DEFAULT_CHUNKS = 65536
CHUNK_BYTES = 1024


def main() -> None:
    chunks = workload_n(DEFAULT_CHUNKS)
    retained, out = run_profiled(lambda: grow(chunks, CHUNK_BYTES))
    print(f"retained {retained_bytes(retained)} bytes in {len(retained)} chunks; heap profile: {out}")


if __name__ == "__main__":
    main()
