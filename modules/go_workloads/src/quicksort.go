// In-place recursive quicksort over seeded random input; the recursion
// gives the flamegraph its Quicksort → partition tower.

package go_workloads

import "math/rand/v2"

func RandomSlice(n int, seed uint64) []uint64 {
	rng := rand.New(rand.NewPCG(seed, seed))
	v := make([]uint64, n)
	for i := range v {
		v[i] = rng.Uint64()
	}
	return v
}

func Quicksort(v []uint64) {
	if len(v) <= 1 {
		return
	}
	mid := partition(v)
	Quicksort(v[:mid])
	Quicksort(v[mid+1:])
}

// partition is Lomuto around the last element; returns the pivot's
// final slot.
func partition(v []uint64) int {
	pivot := v[len(v)-1]
	store := 0
	for i := 0; i < len(v)-1; i++ {
		if v[i] <= pivot {
			v[store], v[i] = v[i], v[store]
			store++
		}
	}
	v[store], v[len(v)-1] = v[len(v)-1], v[store]
	return store
}
