package go_workloads

import (
	"slices"
	"testing"

	"github.com/stretchr/testify/assert"
)

const seed = 42

func TestMatmulLoopOrdersAgree(t *testing.T) {
	n := 16
	a := RandomMatrix(n, seed)
	b := RandomMatrix(n, seed+1)
	// Per-element accumulation order is identical in both variants, so
	// the float results match exactly.
	assert.Equal(t, MultiplyIJK(a, b, n), MultiplyIKJ(a, b, n))
}

func TestQuicksortSorts(t *testing.T) {
	v := RandomSlice(1000, seed)
	expected := slices.Clone(v)
	slices.Sort(expected)
	Quicksort(v)
	assert.Equal(t, expected, v)
}

func TestPointerChaseVisitsEverySlotOnce(t *testing.T) {
	n := 97
	perm := BuildCycle(n, seed)
	expected := n * (n - 1) / 2
	assert.Equal(t, expected, ChaseSum(perm))
	assert.Equal(t, expected, ArraySum(perm))
}

func TestRetainedGrowthRetainsRequestedBytes(t *testing.T) {
	retained := Grow(8, 1024)
	assert.Equal(t, 8*1024, RetainedBytes(retained))
}

func TestStringChurnBuildsFullString(t *testing.T) {
	assert.Len(t, Concat(10, "ab"), 20)
}
