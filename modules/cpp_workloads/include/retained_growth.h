#pragma once

#include <cstddef>
#include <vector>

namespace cpp_workloads {

// Steadily grows a retained, reachable-but-never-reread heap: the
// live-heap signature a profiler attributes to this allocation site.
auto grow(std::size_t chunks, std::size_t chunk_bytes) -> std::vector<std::vector<std::byte>>;

auto retained_bytes(const std::vector<std::vector<std::byte>>& retained) -> std::size_t;

}  // namespace cpp_workloads
