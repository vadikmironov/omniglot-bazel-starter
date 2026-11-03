// Linted under --config=gcc_hermetic by CI, to catch clang-tidy parsing GCC's
// own <immintrin.h> again (see //tools/lint/patches).

#include <immintrin.h>

auto main() -> int { return static_cast<int>(sizeof(__m256) / sizeof(float)); }
