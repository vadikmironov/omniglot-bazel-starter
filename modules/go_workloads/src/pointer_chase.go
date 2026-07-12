// Pointer chasing over a single-cycle permutation versus a contiguous
// sum of the same buffer: dependent random loads against streaming loads.

package go_workloads

import "math/rand/v2"

// BuildCycle returns a single-cycle permutation of 0..n (Sattolo's
// algorithm): following i = perm[i] from any start visits every slot
// exactly once.
func BuildCycle(n int, seed uint64) []int {
	rng := rand.New(rand.NewPCG(seed, seed))
	perm := make([]int, n)
	for i := range perm {
		perm[i] = i
	}
	for i := n - 1; i >= 1; i-- {
		j := rng.IntN(i)
		perm[i], perm[j] = perm[j], perm[i]
	}
	return perm
}

// ChaseSum walks the cycle once from slot 0, summing the visited indices.
func ChaseSum(perm []int) int {
	idx, acc := 0, 0
	for range perm {
		acc += idx
		idx = perm[idx]
	}
	return acc
}

// ArraySum is the streaming counterpart: a contiguous sum of the buffer.
func ArraySum(perm []int) int {
	acc := 0
	for _, v := range perm {
		acc += v
	}
	return acc
}
