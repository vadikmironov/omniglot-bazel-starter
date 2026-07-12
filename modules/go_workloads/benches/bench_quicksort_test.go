// Quicksort bench: recursive call tree renders as a Quicksort →
// partition flamegraph tower, with a branch-miss story on random input.

package go_workloads

import "testing"

const quicksortDefaultN = 1_000_000

func BenchmarkQuicksort(b *testing.B) {
	n := WorkloadN(quicksortDefaultN)
	input := RandomSlice(n, 42)
	buf := make([]uint64, n)
	b.ResetTimer()
	for b.Loop() {
		copy(buf, input)
		Quicksort(buf)
	}
}
