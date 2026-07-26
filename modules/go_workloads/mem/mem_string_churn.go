// One-shot string-churn workload: massive transient allocation traffic
// with a tiny live heap at dump time.

package main

import (
	"fmt"
	"runtime"

	wl "omniglot-bazel-starter/modules/go_workloads"
)

const defaultPieces = 8_000

func main() {
	pieces := wl.WorkloadN(defaultPieces)
	s := wl.Concat(pieces, "0123456789abcdef")
	out := dumpHeapProfile()
	fmt.Printf("built %d bytes; heap profile: %s\n", len(s), out)
	// Without this the accumulator is dead by dump time — `len(s)` needs only
	// the length, so the compiler drops the reference and the GC inside the
	// dump collects the very object the workload exists to show. The live heap
	// is meant to be tiny, not empty (cf. mem_retained_growth.go).
	runtime.KeepAlive(s)
}
