#include <fmt/base.h>

// fmt::println comes from <fmt/base.h>, the lightweight core of {fmt}. The
// library was compiled from its upstream CMakeLists.txt by the cmake() rule in
// this module's BUILD and linked in as a plain cc_binary dep. rules_foreign_cc
// builds fmt with the same toolchain as this binary, so the banner below
// reports the compiler used for both.
auto main() -> int {
#ifdef __clang__
    fmt::println(">> using clang++ {}.{}.{} ({})", __clang_major__, __clang_minor__, __clang_patchlevel__, __cplusplus);
#elifdef _MSC_VER
    fmt::println(">> using MSVC {} ({})", _MSC_VER, __cplusplus);
#elifdef __GNUC__
    fmt::println(">> using gcc++ {}.{}.{} ({})", __GNUC__, __GNUC_MINOR__, __GNUC_PATCHLEVEL__, __cplusplus);
#else
    fmt::println(">> unknown compiler ({})", __cplusplus);
#endif

    fmt::println("Hello, World! Printed by fmt, built from CMake via rules_foreign_cc.");
}
