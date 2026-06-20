#include <gtest/gtest.h>

#include "cpp_library.h"

namespace cpp_library {

// NOLINTBEGIN(cppcoreguidelines-avoid-non-const-global-variables,cppcoreguidelines-owning-memory,cert-err58-cpp,modernize-use-trailing-return-type)
TEST(HelloWorldStringPrinterTest, DefaultLevelReturnsHelloWorld) {
    EXPECT_EQ(HelloWorldStringPrinter::get_hello_world_string(0), "Hello, World!");
    EXPECT_EQ(HelloWorldStringPrinter::get_hello_world_string(3), "Hello, World!");
    EXPECT_EQ(HelloWorldStringPrinter::get_hello_world_string(100), "Hello, World!");
}

TEST(HelloWorldStringPrinterTest, SpecificLevelReturnsHelloWorld) {
    EXPECT_EQ(HelloWorldStringPrinter::get_hello_world_string(1), "Hello, Star!");
    EXPECT_EQ(HelloWorldStringPrinter::get_hello_world_string(2), "Hello, Superstar!");
    EXPECT_EQ(HelloWorldStringPrinter::get_hello_world_string(3), "Hello, World!");
}
// NOLINTEND(cppcoreguidelines-avoid-non-const-global-variables,cppcoreguidelines-owning-memory,cert-err58-cpp,modernize-use-trailing-return-type)

}  // namespace cpp_library
