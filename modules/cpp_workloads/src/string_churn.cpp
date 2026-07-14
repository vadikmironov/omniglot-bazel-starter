#include "string_churn.h"

#include <cstddef>
#include <string>
#include <string_view>

namespace cpp_workloads {

auto concat(std::size_t pieces, std::string_view piece) -> std::string {
    std::string acc;
    for (std::size_t i = 0; i < pieces; i++) {
        // Rebuild instead of append: forces the fresh-allocation-and-copy
        // churn this workload exists to show.
        std::string next;
        next.reserve(acc.size() + piece.size());
        next.append(acc);
        next.append(piece);
        acc = std::move(next);
    }
    return acc;
}

}  // namespace cpp_workloads
