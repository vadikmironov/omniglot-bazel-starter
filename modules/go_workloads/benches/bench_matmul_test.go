// Matrix-multiply bench: the ijk vs ikj loop-order gap is cache
// behaviour — in-process profiles show a hot loop, an external
// sampler's cache counters explain the difference.

package go_workloads

import "testing"

const matmulDefaultN = 256

func BenchmarkMatmulIJK(b *testing.B) {
	n := WorkloadN(matmulDefaultN)
	x := RandomMatrix(n, 42)
	y := RandomMatrix(n, 43)
	b.ResetTimer()
	for b.Loop() {
		MultiplyIJK(x, y, n)
	}
}

func BenchmarkMatmulIKJ(b *testing.B) {
	n := WorkloadN(matmulDefaultN)
	x := RandomMatrix(n, 42)
	y := RandomMatrix(n, 43)
	b.ResetTimer()
	for b.Loop() {
		MultiplyIKJ(x, y, n)
	}
}
