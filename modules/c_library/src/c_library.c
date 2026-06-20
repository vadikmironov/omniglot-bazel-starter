#include "c_library.h"

#include <stdio.h>

void println_str_native(int level, get_hello_world_str_fcn func) {
    const char* str = func(level);
    printf("println_str_native: %s\n", str);
}