// Package go_workloads holds profiling workloads: deterministic,
// size-tunable kernels with distinct CPU and memory signatures,
// exercised by the bench_* and mem_* targets.
package go_workloads

import (
	"os"
	"strconv"
)

// WorkloadN returns the workload size from WORKLOAD_N, falling back to
// the target's default.
func WorkloadN(fallback int) int {
	if v, err := strconv.Atoi(os.Getenv("WORKLOAD_N")); err == nil {
		return v
	}
	return fallback
}
