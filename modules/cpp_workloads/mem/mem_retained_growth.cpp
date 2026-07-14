// One-shot retained-growth workload: the heap profile attributes the
// whole live heap to the growth site.

#include <cstddef>
#include <cstdio>

#include "prof_dump.h"
#include "retained_growth.h"
#include "workload_n.h"

namespace {
constexpr std::size_t DEFAULT_CHUNKS = 65536;
constexpr std::size_t CHUNK_BYTES = 1024;
}  // namespace

auto main() -> int {
    const std::size_t chunks = cpp_workloads::workload_n(DEFAULT_CHUNKS);
    cpp_workloads::heap_profile_start();
    const auto retained = cpp_workloads::grow(chunks, CHUNK_BYTES);
    const auto out = cpp_workloads::heap_profile_dump();
    std::printf("retained %zu bytes in %zu chunks; heap profile prefix: %s\n",
                cpp_workloads::retained_bytes(retained), retained.size(), out.c_str());
    return 0;
}
