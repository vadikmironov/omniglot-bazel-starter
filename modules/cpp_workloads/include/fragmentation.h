#pragma once

#include <cstddef>
#include <cstdint>
#include <utility>
#include <vector>

namespace cpp_workloads {

struct FragStats {
    std::size_t survivors;
    std::size_t live_bytes;
};

// Fragmentation: allocate many variably sized blocks, free every other one,
// then grow each survivor — live bytes shrink while the allocator's mapped
// memory stays high. Returns the surviving blocks (hold them alive while
// the heap profile is dumped) and their stats.
auto fragment(std::size_t blocks, std::uint64_t seed)
    -> std::pair<std::vector<std::vector<std::byte>>, FragStats>;

}  // namespace cpp_workloads
