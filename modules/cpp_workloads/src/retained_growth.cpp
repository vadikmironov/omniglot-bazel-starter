#include "retained_growth.h"

#include <cstddef>
#include <utility>
#include <vector>

namespace cpp_workloads {

namespace {

// Prime modulus: every chunk gets a distinct fill byte, so nothing dedups.
constexpr std::size_t FILL_MODULUS = 251;

}  // namespace

auto grow(std::size_t chunks, std::size_t chunk_bytes) -> std::vector<std::vector<std::byte>> {
    std::vector<std::vector<std::byte>> retained;
    retained.reserve(chunks);
    for (std::size_t i = 0; i < chunks; i++) {
        std::vector<std::byte> chunk(chunk_bytes);
        for (auto& b : chunk) {
            b = static_cast<std::byte>(i % FILL_MODULUS);
        }
        retained.push_back(std::move(chunk));
    }
    return retained;
}

auto retained_bytes(const std::vector<std::vector<std::byte>>& retained) -> std::size_t {
    std::size_t total = 0;
    for (const auto& chunk : retained) {
        total += chunk.size();
    }
    return total;
}

}  // namespace cpp_workloads
