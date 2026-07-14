#include "prof_dump.h"

#include <gperftools/heap-profiler.h>

#include <cstdlib>
#include <string>

namespace cpp_workloads {

void heap_profile_start() {
    const char* out = std::getenv("MEMPROF_OUT");
    if (out != nullptr) {
        HeapProfilerStart(out);
    }
}

auto heap_profile_dump() -> std::string {
    const char* out = std::getenv("MEMPROF_OUT");
    if (out == nullptr) {
        return "";
    }
    HeapProfilerDump("workload done");
    HeapProfilerStop();
    return out;
}

}  // namespace cpp_workloads
