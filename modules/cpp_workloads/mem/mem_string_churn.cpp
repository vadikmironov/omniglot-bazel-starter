// One-shot string-churn workload: massive transient allocation traffic
// with a tiny live heap at dump time.

#include <cstddef>
#include <cstdio>

#include "prof_dump.h"
#include "string_churn.h"
#include "workload_n.h"

namespace {
constexpr std::size_t DEFAULT_PIECES = 8000;
}  // namespace

auto main() -> int {
    const std::size_t pieces = cpp_workloads::workload_n(DEFAULT_PIECES);
    cpp_workloads::heap_profile_start();
    const auto s = cpp_workloads::concat(pieces, "0123456789abcdef");
    const auto out = cpp_workloads::heap_profile_dump();
    std::printf("built %zu bytes; heap profile prefix: %s\n", s.size(), out.c_str());
    return 0;
}
