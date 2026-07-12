// One-shot string-churn workload: massive transient allocation traffic
// with a tiny live heap at dump time.

package main

import (
	"fmt"

	wl "omniglot-bazel-starter/modules/go_workloads"
)

const defaultPieces = 8_000

func main() {
	pieces := wl.WorkloadN(defaultPieces)
	s := wl.Concat(pieces, "0123456789abcdef")
	out := dumpHeapProfile()
	fmt.Printf("built %d bytes; heap profile: %s\n", len(s), out)
}
