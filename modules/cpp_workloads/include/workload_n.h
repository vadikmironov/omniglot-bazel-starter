#pragma once

#include <charconv>
#include <cstddef>
#include <cstdlib>
#include <cstring>
#include <system_error>

namespace cpp_workloads {

// Workload size from WORKLOAD_N, falling back to the target's default.
// from_chars rejects signs on unsigned types and reports overflow, so a
// negative or oversized value keeps the default instead of wrapping to
// SIZE_MAX the way strtoull would.
inline auto workload_n(std::size_t fallback) -> std::size_t {
    const char* raw = std::getenv("WORKLOAD_N");
    if (raw == nullptr) {
        return fallback;
    }
    std::size_t parsed = 0;
    const char* last = raw + std::strlen(raw);
    const auto [ptr, ec] = std::from_chars(raw, last, parsed);
    if (ec != std::errc{} || ptr != last) {
        return fallback;
    }
    return parsed;
}

}  // namespace cpp_workloads
