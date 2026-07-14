#include "matmul.h"

#include <cstddef>
#include <cstdint>
#include <random>
#include <vector>

namespace cpp_workloads {

auto random_matrix(std::size_t n, std::uint64_t seed) -> std::vector<double> {
    std::mt19937_64 rng(seed);
    std::uniform_real_distribution<double> dist(0.0, 1.0);
    std::vector<double> m(n * n);
    for (auto& v : m) {
        v = dist(rng);
    }
    return m;
}

auto multiply_ijk(const std::vector<double>& a, const std::vector<double>& b, std::size_t n)
    -> std::vector<double> {
    std::vector<double> c(n * n);
    for (std::size_t i = 0; i < n; i++) {
        for (std::size_t j = 0; j < n; j++) {
            double acc = 0.0;
            for (std::size_t k = 0; k < n; k++) {
                acc += a[(i * n) + k] * b[(k * n) + j];
            }
            c[(i * n) + j] = acc;
        }
    }
    return c;
}

auto multiply_ikj(const std::vector<double>& a, const std::vector<double>& b, std::size_t n)
    -> std::vector<double> {
    std::vector<double> c(n * n);
    for (std::size_t i = 0; i < n; i++) {
        for (std::size_t k = 0; k < n; k++) {
            const double aik = a[(i * n) + k];
            for (std::size_t j = 0; j < n; j++) {
                c[(i * n) + j] += aik * b[(k * n) + j];
            }
        }
    }
    return c;
}

}  // namespace cpp_workloads
