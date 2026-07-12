// One-shot retained-growth workload: the heap profile attributes the
// whole live heap to the growth site.

package main

import (
	"fmt"
	"runtime"

	wl "omniglot-bazel-starter/modules/go_workloads"
)

const (
	defaultChunks = 65_536
	chunkBytes    = 1024
)

func main() {
	chunks := wl.WorkloadN(defaultChunks)
	retained := wl.Grow(chunks, chunkBytes)
	out := dumpHeapProfile()
	fmt.Printf("retained %d bytes in %d chunks; heap profile: %s\n",
		wl.RetainedBytes(retained), len(retained), out)
	runtime.KeepAlive(retained)
}
