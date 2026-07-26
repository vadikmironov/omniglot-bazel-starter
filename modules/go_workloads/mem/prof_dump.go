// Shared shim for the one-shot memory workloads: the runtime's heap
// profile dumped as pprof while the workload's heap is live, plus the
// footprint sidecar the //tools/profile runner folds into its report.

package main

import (
	"fmt"
	"os"
	"runtime"
	"runtime/pprof"
	"strconv"
	"strings"
)

// memProfileRate samples one allocation per 32 KiB. Go is the only language
// here whose heap profile is sampled at all — C++, Rust and Python record
// every allocation — so it is the only one that needs an error bar. The
// 512 KiB default hides small live heaps entirely: the churn workload's
// ~128 KB final string is sampled barely a fifth of the time, so its
// live-heap profile comes out as scaled noise.
// runtime/pprof unsamples using the rate current at write time, so
// allocations made by imported packages' init (before this runs) are scaled
// with the new rate; they are almost all freed by dump time, so the skew is
// confined to frames that report zero live bytes anyway.
const memProfileRate = 32 * 1024

func init() {
	runtime.MemProfileRate = memProfileRate
}

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
	writeMeta(out)
	return out
}

// writeMeta records footprint and precision alongside the profile:
// live bytes over VmRSS is the only signal that separates fragmentation from
// genuine retention, and the sampling rate tells the runner how far to trust
// the unsampled live-heap figures.
func writeMeta(out string) {
	rss, hwm := readRSS()
	meta := fmt.Sprintf("vmrss_bytes=%d\nvmhwm_bytes=%d\nprecision=sampled_bytes:%d\n",
		rss, hwm, runtime.MemProfileRate)
	// Best-effort: a missing sidecar only costs the footprint ratios.
	_ = os.WriteFile(out+".meta", []byte(meta), 0o644)
}

// readRSS returns current and peak resident set size in bytes, or zeroes
// where /proc is unavailable (macOS).
func readRSS() (current, peak int64) {
	status, err := os.ReadFile("/proc/self/status")
	if err != nil {
		return 0, 0
	}
	for _, line := range strings.Split(string(status), "\n") {
		field, value, found := strings.Cut(line, ":")
		if !found {
			continue
		}
		switch field {
		case "VmRSS":
			current = parseKiB(value)
		case "VmHWM":
			peak = parseKiB(value)
		}
	}
	return current, peak
}

func parseKiB(value string) int64 {
	kib, err := strconv.ParseInt(strings.TrimSuffix(strings.TrimSpace(value), " kB"), 10, 64)
	if err != nil {
		return 0
	}
	return kib * 1024
}
