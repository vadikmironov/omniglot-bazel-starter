// Pointer-chase bench: serially dependent random loads (memory-latency
// bound) against a contiguous sum of the same buffer (bandwidth bound).

package go_workloads

import "testing"

const chaseDefaultN = 1 << 22

func BenchmarkChase(b *testing.B) {
	perm := BuildCycle(WorkloadN(chaseDefaultN), 42)
	b.ResetTimer()
	for b.Loop() {
		ChaseSum(perm)
	}
}

func BenchmarkArraySum(b *testing.B) {
	perm := BuildCycle(WorkloadN(chaseDefaultN), 42)
	b.ResetTimer()
	for b.Loop() {
		ArraySum(perm)
	}
}
