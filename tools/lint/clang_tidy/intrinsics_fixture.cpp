// A lint fixture for the wrapper in main.cpp, linted under
// --config=gcc_hermetic. GCC's <immintrin.h> doesn't parse with clang, and
// <semaphore> needs the system's <limits.h>, which clang's reaches only when
// GCC's own headers are gone. So its lint test fails if the wrapper leaves
// GCC's header directory in place, or keeps it behind clang's.

#include <immintrin.h>

#include <semaphore>

auto main() -> int {
    std::binary_semaphore semaphore(1);
    semaphore.acquire();
    return static_cast<int>(sizeof(__m256) / sizeof(float));
}
