// Steadily grows a retained, reachable-but-never-reread heap: the
// live-heap signature a profiler attributes to this allocation site.

package go_workloads

// Grow allocates chunks chunks of chunkBytes each and retains them all.
// The caller must hold the result alive while the heap profile is dumped.
func Grow(chunks, chunkBytes int) [][]byte {
	retained := make([][]byte, 0, chunks)
	for i := 0; i < chunks; i++ {
		chunk := make([]byte, chunkBytes)
		for j := range chunk {
			chunk[j] = byte(i % 251)
		}
		retained = append(retained, chunk)
	}
	return retained
}

func RetainedBytes(retained [][]byte) int {
	total := 0
	for _, c := range retained {
		total += len(c)
	}
	return total
}
