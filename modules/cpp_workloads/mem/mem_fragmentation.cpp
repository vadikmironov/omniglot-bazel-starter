// One-shot fragmentation workload: live bytes drop while tcmalloc's
// mapped memory stays high.

#include <cstddef>
#include <cstdio>

#include "fragmentation.h"
#include "prof_dump.h"
#include "workload_n.h"

namespace {
constexpr std::size_t DEFAULT_BLOCKS = 50000;
}  // namespace

auto main() -> int {
    const std::size_t blocks = cpp_workloads::workload_n(DEFAULT_BLOCKS);
    cpp_workloads::heap_profile_start();
    const auto [survivors, stats] = cpp_workloads::fragment(blocks, 42);
    const auto out = cpp_workloads::heap_profile_dump();
    std::printf("%zu surviving blocks, %zu live bytes; heap profile prefix: %s\n",
                stats.survivors, stats.live_bytes, out.c_str());
    return 0;
}
