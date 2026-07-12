// Shared shim for the one-shot memory workloads: the runtime's heap
// profile dumped as pprof while the workload's heap is live.

package main

import (
	"os"
	"runtime"
	"runtime/pprof"
)

// dumpHeapProfile writes a heap profile to $MEMPROF_OUT (default
// memprof.pb) and returns the path. Call it while the workload's heap
// is still live.
func dumpHeapProfile() string {
	out := os.Getenv("MEMPROF_OUT")
	if out == "" {
		out = "memprof.pb"
	}
	// Flush recent allocations into the profile's live set.
	runtime.GC()
	f, err := os.Create(out)
	if err != nil {
		panic(err)
	}
	defer f.Close()
	if err := pprof.Lookup("heap").WriteTo(f, 0); err != nil {
		panic(err)
	}
	return out
}
