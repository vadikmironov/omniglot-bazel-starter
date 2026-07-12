// O(n²) string concatenation: strings are immutable, so every round
// allocates a fresh string and copies the whole accumulator — high
// transient allocation rate, tiny live heap at any instant.

package go_workloads

func Concat(pieces int, piece string) string {
	acc := ""
	for i := 0; i < pieces; i++ {
		acc += piece
	}
	return acc
}
