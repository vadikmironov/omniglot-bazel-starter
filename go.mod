module omniglot-bazel-starter

go 1.26.0

require (
	github.com/bazelbuild/bazel-gazelle v0.53.0
	github.com/stretchr/testify v1.11.1
)

require (
	github.com/bazel-contrib/bazel-gazelle/v2 v2.0.0-3 // indirect
	github.com/bazelbuild/buildtools v0.0.0-20250930140053-2eb4fccefb52 // indirect
	github.com/chzyer/readline v1.5.1 // indirect
	github.com/ianlancetaylor/demangle v0.0.0-20250417193237-f615e6bd150b // indirect
	github.com/kr/text v0.2.0 // indirect
	golang.org/x/mod v0.23.0 // indirect
	golang.org/x/sys v0.47.0 // indirect
	golang.org/x/tools/go/vcs v0.1.0-deprecated // indirect
	gopkg.in/check.v1 v1.0.0-20201130134442-10cb98267c6c // indirect
)

// --- BEGIN exclude ---
require golang.org/x/net v0.58.0

// --- END exclude ---

require (
	github.com/BurntSushi/toml v1.6.0
	github.com/davecgh/go-spew v1.1.2-0.20180830191138-d8f796af33cc // indirect
	// --- BEGIN feature:profiling ---
	// Imported directly by //tools/profile/pb2folded, so this is needed by
	// every profiling scaffold — not just the C++ one, which additionally
	// runs the pprof CLI as a tool (below).
	github.com/google/pprof v0.0.0-20260802141513-ef3492d7dac3
	// --- END feature:profiling ---
	github.com/pmezard/go-difflib v1.0.1-0.20181226105442-5d4384ee4fb2 // indirect
	gopkg.in/yaml.v3 v3.0.1 // indirect
)

// --- BEGIN feature:profiling lang:cpp ---
// Converts + symbolizes gperftools' legacy profile format against the bench
// binary's ELF symtab; the C++ capture path can't emit symbolized protos
// in-process the way Go/Rust do.
tool github.com/google/pprof

// --- END feature:profiling lang:cpp ---
