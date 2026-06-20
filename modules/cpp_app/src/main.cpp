#include <iostream>

#include "cpp_library.h"

auto main(int /*argc*/, char** /*argv*/) -> int {
#ifdef __clang__
    std::cout << ">> using clang++ " << __clang_major__ << "." << __clang_minor__ << "." << __clang_patchlevel__ << " (" << __cplusplus << ")\n";
#elifdef _MSC_VER
    std::cout << ">> using MSVC " << _MSC_VER << " (" << __cplusplus << ")\n";
#elifdef __GNUC__
    std::cout << ">> using gcc++ " << __GNUC__ << "." << __GNUC_MINOR__ << "." << __GNUC_PATCHLEVEL__ << " (" << __cplusplus << ")\n";
#else
    std::cout << ">> unknown compiler" << " (" << __cplusplus << ")\n";
#endif

    std::cout
        << cpp_library::HelloWorldStringPrinter::get_hello_world_string(3) << '\n';
}