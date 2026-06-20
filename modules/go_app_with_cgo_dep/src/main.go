// Command go_app_with_cgo_dep is a cgo example adapted from
// https://go.dev/wiki/cgo for a Bazel build.
//
// Two cgo gotchas worth keeping in mind, both about placement:
//
//   - The C preamble (the /* ... */ block below) must sit directly above
//     `import "C"` — no blank line, comment, or code in between. A gap
//     detaches it, so cgo compiles an empty preamble and every C.* reference
//     fails with "could not determine what C.x refers to". (Blank lines
//     inside the preamble are fine — that text is just C.)
//   - `import "C"` must be its own statement, never folded into a grouped
//     `import ( ... )` block like the one below.
package main

/*
#include "c_library.h"

// Forward declaration of the C gateway; its body lives in cfuncs.go.
char* get_hello_world_string_cgo(int);
*/
import "C"

import (
	"fmt"
	"runtime"
	"unsafe"
)

// C.CString mallocs on the C heap, which Go's GC never tracks. These live
// for the whole program, so we intentionally don't free them — the OS
// reclaims them at exit. A CString made per call would instead need
// `defer C.free(unsafe.Pointer(p))`.
var (
	hello_world_cstr     *C.char = C.CString("Hello, World!")
	hello_star_cstr      *C.char = C.CString("Hello, Star!")
	hello_superstar_cstr *C.char = C.CString("Hello, Superstar!")
)

// get_hello_world_string is called from C, via the gateway in cfuncs.go.
// The //export directive (no space after //) makes a Go function C-callable.
// Gotcha: a file using //export may have only declarations in its preamble,
// never definitions — which is why the gateway's body lives in cfuncs.go.
//
//export get_hello_world_string
func get_hello_world_string(level int) *C.char {
	switch level {
	case 1:
		return hello_star_cstr
	case 2:
		return hello_superstar_cstr
	default:
		return hello_world_cstr
	}
}

func main() {
	fmt.Println(">> built by " + runtime.Version())

	// Pass C a pointer to the C gateway (not the Go function directly): C
	// calls the gateway, which calls back into the exported Go function.
	// unsafe.Pointer + the cast to the C typedef bridge the two views of the
	// function-pointer type.
	C.println_str_native(3, C.get_hello_world_str_fcn(unsafe.Pointer(C.get_hello_world_string_cgo)))
}
