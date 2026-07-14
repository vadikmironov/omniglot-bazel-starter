"""One-shot string-churn workload: massive transient allocation traffic
with a tiny live heap at dump time."""

from prof_dump import run_profiled
from python_workloads.string_churn import concat
from python_workloads.workload_n import workload_n

DEFAULT_PIECES = 8000


def main() -> None:
    pieces = workload_n(DEFAULT_PIECES)
    s, out = run_profiled(lambda: concat(pieces, "0123456789abcdef"))
    print(f"built {len(s)} chars; heap profile: {out}")


if __name__ == "__main__":
    main()
