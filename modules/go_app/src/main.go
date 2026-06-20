package main

import (
	"fmt"
	"modules/go_lib"
	"runtime"
)

func main() {
	fmt.Println(">> built by " + runtime.Version())

	fmt.Println(go_lib.GetHelloWorldString(3))
}
