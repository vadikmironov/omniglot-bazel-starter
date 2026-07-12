// Dense n×n matrix multiply in two loop orders: ijk strides column-wise
// through b (cache-hostile), ikj streams both operands row-major.

package go_workloads

import "math/rand/v2"

// RandomMatrix returns a row-major n×n matrix filled from a seeded PRNG.
func RandomMatrix(n int, seed uint64) []float64 {
	rng := rand.New(rand.NewPCG(seed, seed))
	m := make([]float64, n*n)
	for i := range m {
		m[i] = rng.Float64()
	}
	return m
}

func MultiplyIJK(a, b []float64, n int) []float64 {
	c := make([]float64, n*n)
	for i := 0; i < n; i++ {
		for j := 0; j < n; j++ {
			acc := 0.0
			for k := 0; k < n; k++ {
				acc += a[i*n+k] * b[k*n+j]
			}
			c[i*n+j] = acc
		}
	}
	return c
}

func MultiplyIKJ(a, b []float64, n int) []float64 {
	c := make([]float64, n*n)
	for i := 0; i < n; i++ {
		for k := 0; k < n; k++ {
			aik := a[i*n+k]
			for j := 0; j < n; j++ {
				c[i*n+j] += aik * b[k*n+j]
			}
		}
	}
	return c
}
