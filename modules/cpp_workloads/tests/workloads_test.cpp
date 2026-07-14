#include <gtest/gtest.h>

#include <algorithm>
#include <cstddef>
#include <vector>

#include "fragmentation.h"
#include "matmul.h"
#include "pointer_chase.h"
#include "quicksort.h"
#include "retained_growth.h"
#include "string_churn.h"

namespace {

constexpr std::uint64_t SEED = 42;

TEST(Workloads, MatmulLoopOrdersAgree) {
    const std::size_t n = 16;
    const auto a = cpp_workloads::random_matrix(n, SEED);
    const auto b = cpp_workloads::random_matrix(n, SEED + 1);
    // Per-element accumulation order is identical in both variants, so
    // the float results match exactly.
    EXPECT_EQ(cpp_workloads::multiply_ijk(a, b, n), cpp_workloads::multiply_ikj(a, b, n));
}

TEST(Workloads, QuicksortSorts) {
    auto v = cpp_workloads::random_slice(1000, SEED);
    auto expected = v;
    std::ranges::sort(expected);
    cpp_workloads::quicksort(v);
    EXPECT_EQ(expected, v);
}

TEST(Workloads, PointerChaseVisitsEverySlotOnce) {
    const std::size_t n = 97;
    const auto perm = cpp_workloads::build_cycle(n, SEED);
    const std::size_t expected = n * (n - 1) / 2;
    EXPECT_EQ(expected, cpp_workloads::chase_sum(perm));
    EXPECT_EQ(expected, cpp_workloads::array_sum(perm));
}

TEST(Workloads, RetainedGrowthRetainsRequestedBytes) {
    const auto retained = cpp_workloads::grow(8, 1024);
    EXPECT_EQ(8 * 1024, cpp_workloads::retained_bytes(retained));
}

TEST(Workloads, StringChurnBuildsFullString) {
    EXPECT_EQ(20, cpp_workloads::concat(10, "ab").size());
}

TEST(Workloads, FragmentationKeepsEveryOtherBlockDoubled) {
    const auto [survivors, stats] = cpp_workloads::fragment(9, SEED);
    EXPECT_EQ(5, stats.survivors);
    EXPECT_EQ(survivors.size(), stats.survivors);
    std::size_t total = 0;
    for (const auto& block : survivors) {
        // Doubled from the initial 512..8191 draw.
        EXPECT_GE(block.size(), 2 * 512);
        EXPECT_LT(block.size(), 2 * 8192);
        total += block.size();
    }
    EXPECT_EQ(total, stats.live_bytes);
}

}  // namespace
