#include "fragmentation.h"

#include <cstddef>
#include <cstdint>
#include <random>
#include <utility>
#include <vector>

namespace cpp_workloads {

auto fragment(std::size_t blocks, std::uint64_t seed)
    -> std::pair<std::vector<std::vector<std::byte>>, FragStats> {
    std::mt19937_64 rng(seed);
    std::uniform_int_distribution<std::size_t> size_dist(512, 8191);

    std::vector<std::vector<std::byte>> all;
    all.reserve(blocks);
    for (std::size_t i = 0; i < blocks; i++) {
        all.emplace_back(size_dist(rng), std::byte{0xA5});
    }

    std::vector<std::vector<std::byte>> survivors;
    survivors.reserve((blocks + 1) / 2);
    for (std::size_t i = 0; i < all.size(); i++) {
        if (i % 2 == 0) {
            survivors.push_back(std::move(all[i]));
        }
    }
    all.clear();
    all.shrink_to_fit();
    for (auto& block : survivors) {
        block.resize(block.size() * 2, std::byte{0x5A});
    }

    FragStats stats{.survivors = survivors.size(), .live_bytes = 0};
    for (const auto& block : survivors) {
        stats.live_bytes += block.size();
    }
    return {std::move(survivors), stats};
}

}  // namespace cpp_workloads
