package main

// This file holds the C gateway and is deliberately separate from main.go:
// main.go uses //export, and a //export file's preamble may contain only C
// declarations, not definitions. The gateway below is a definition, so it
// lives here, in a file without //export. Both files are package main, so
// the gateway and the exported callback see each other with no import.

/*
#include <stdio.h>

// The gateway is C-callable, but its job is to call back into Go.
char* get_hello_world_string_cgo(int level)
{
    printf("C.get_hello_world_string_cgo(): called with arg = %d\n", level);

    // Forward declaration of the Go function exported from main.go; cgo
    // emits it as a C-linkage symbol this file can call.
    char* get_hello_world_string(int);
    return get_hello_world_string(level);
}
*/
import "C"
