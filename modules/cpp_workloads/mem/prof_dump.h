#pragma once

#include <string>

namespace cpp_workloads {

// Shared shim for the one-shot memory workloads: tcmalloc's heap profiler
// dumped in gperftools' legacy format while the workload's heap is live
// (the //tools/profile runner converts it to pprof). Both calls are no-ops
// unless MEMPROF_OUT is set; heap_profile_start must run before the
// workload allocates — tcmalloc only tracks allocations made after it.
void heap_profile_start();

// Dumps to <MEMPROF_OUT>.NNNN.heap and returns the prefix. Call it while
// the workload's heap is still live.
auto heap_profile_dump() -> std::string;

}  // namespace cpp_workloads
