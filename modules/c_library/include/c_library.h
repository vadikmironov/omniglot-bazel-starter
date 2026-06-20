#pragma once

typedef char* (*get_hello_world_str_fcn)(int);
void println_str_native(int, get_hello_world_str_fcn);