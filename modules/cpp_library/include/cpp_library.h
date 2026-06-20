#pragma once

#include <string_view>

namespace cpp_library {
class HelloWorldStringPrinter {
public:
    static const unsigned int DEFAULT_LEVEL = 0;

    static auto get_hello_world_string(unsigned int level) -> std::string_view;
};
}  // namespace cpp_library