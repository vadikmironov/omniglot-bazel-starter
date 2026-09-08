#include "prof_dump.h"

#include <gperftools/heap-profiler.h>

#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <string>

namespace cpp_workloads {

namespace {

constexpr std::int64_t BYTES_PER_KIB = 1024;

// Resident set size in bytes, current and peak, or zero where /proc is
// unavailable (macOS).
struct Footprint {
    std::int64_t current;
    std::int64_t peak;
};

auto read_rss() -> Footprint {
    std::ifstream status("/proc/self/status");
    Footprint footprint{.current = 0, .peak = 0};
    std::string field;
    while (status >> field) {
        const bool is_rss = field == "VmRSS:";
        if (!is_rss && field != "VmHWM:") {
            continue;
        }
        std::int64_t kib = 0;
        if (!(status >> kib)) {
            break;
        }
        (is_rss ? footprint.current : footprint.peak) = kib * BYTES_PER_KIB;
    }
    return footprint;
}

// Live bytes over VmRSS is the only signal separating fragmentation from
// genuine retention; tcmalloc records every allocation rather than sampling,
// so the figures are exact and the runner never discounts them.
void write_meta(const std::string& prefix) {
    const auto [current, peak] = read_rss();
    std::ofstream meta(prefix + ".meta");
    if (!meta) {
        return;  // Best-effort: only the footprint ratios are lost.
    }
    meta << "vmrss_bytes=" << current << "\n"
         << "vmhwm_bytes=" << peak << "\n"
         << "precision=exact\n";
}

}  // namespace

void heap_profile_start() {
    const char* out = std::getenv("MEMPROF_OUT");  // NOLINT(concurrency-mt-unsafe): read before any thread starts
    if (out != nullptr) {
        HeapProfilerStart(out);
    }
}

auto heap_profile_dump() -> std::string {
    const char* out = std::getenv("MEMPROF_OUT");  // NOLINT(concurrency-mt-unsafe): read before any thread starts
    if (out == nullptr) {
        return "";
    }
    HeapProfilerDump("workload done");
    HeapProfilerStop();
    write_meta(out);
    return out;
}

}  // namespace cpp_workloads
