#include "cpp_library.h"

#include <string_view>

constexpr std::string_view hello_world_sv = "Hello, World!";
constexpr std::string_view hello_star_sv = "Hello, Star!";
constexpr std::string_view hello_superstar_sv = "Hello, Superstar!";

namespace cpp_library {

auto HelloWorldStringPrinter::get_hello_world_string(unsigned int level)
    -> std::string_view {
    switch (level) {
        case 1:
            return hello_star_sv;
        case 2:
            return hello_superstar_sv;
        case DEFAULT_LEVEL:
        default:
            return hello_world_sv;
    }
}
}  // namespace cpp_library