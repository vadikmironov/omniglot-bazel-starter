module omniglot-bazel-starter

go 1.25.0

require (
	github.com/bazelbuild/bazel-gazelle v0.51.3
	github.com/stretchr/testify v1.11.1
)

require (
	github.com/DataDog/appsec-internal-go v1.5.0 // indirect
	github.com/DataDog/datadog-agent/pkg/obfuscate v0.48.0 // indirect
	github.com/DataDog/datadog-agent/pkg/remoteconfig/state v0.48.1 // indirect
	github.com/DataDog/datadog-go/v5 v5.3.0 // indirect
	github.com/DataDog/go-libddwaf/v2 v2.3.2 // indirect
	github.com/DataDog/go-tuf v1.0.2-0.5.2 // indirect
	github.com/DataDog/gostackparse v0.7.0 // indirect
	github.com/DataDog/sketches-go v1.4.2 // indirect
	github.com/Microsoft/go-winio v0.6.1 // indirect
	github.com/bazel-contrib/bazel-gazelle/v2 v2.0.0-2 // indirect
	github.com/bazelbuild/buildtools v0.0.0-20250930140053-2eb4fccefb52 // indirect
	github.com/cespare/xxhash/v2 v2.2.0 // indirect
	github.com/chzyer/readline v1.5.1 // indirect
	github.com/dustin/go-humanize v1.0.1 // indirect
	github.com/felixge/httpsnoop v1.0.3 // indirect
	github.com/golang/protobuf v1.5.4 // indirect
	github.com/google/uuid v1.3.1 // indirect
	github.com/hashicorp/errwrap v1.1.0 // indirect
	github.com/hashicorp/go-multierror v1.1.1 // indirect
	github.com/ianlancetaylor/demangle v0.0.0-20250417193237-f615e6bd150b // indirect
	github.com/julienschmidt/httprouter v1.3.0 // indirect
	github.com/outcaste-io/ristretto v0.2.3 // indirect
	github.com/peterbourgon/ff/v3 v3.1.0 // indirect
	github.com/philhofer/fwd v1.1.2 // indirect
	github.com/pkg/errors v0.9.1 // indirect
	github.com/richardartoul/molecule v1.0.1-0.20221107223329-32cfee06a052 // indirect
	github.com/secure-systems-lab/go-securesystemslib v0.7.0 // indirect
	github.com/spaolacci/murmur3 v1.1.0 // indirect
	github.com/tinylib/msgp v1.1.8 // indirect
	github.com/wolfeidau/humanhash v1.1.0 // indirect
	go.uber.org/atomic v1.11.0 // indirect
	golang.org/x/mod v0.23.0 // indirect
	golang.org/x/sync v0.11.0 // indirect
	golang.org/x/sys v0.46.0 // indirect
	golang.org/x/time v0.3.0 // indirect
	golang.org/x/tools v0.30.0 // indirect
	golang.org/x/tools/go/vcs v0.1.0-deprecated // indirect
	golang.org/x/xerrors v0.0.0-20220907171357-04be3eba64a2 // indirect
	google.golang.org/protobuf v1.36.3 // indirect
	gopkg.in/DataDog/dd-trace-go.v1 v1.62.0 // indirect
)

// --- BEGIN exclude ---
require golang.org/x/net v0.56.0

// --- END exclude ---

require (
	github.com/BurntSushi/toml v1.6.0
	github.com/davecgh/go-spew v1.1.2-0.20180830191138-d8f796af33cc // indirect
	// --- BEGIN feature:profiling ---
	github.com/ebitengine/purego v0.10.1 // indirect
	github.com/felixge/pprofutils/v2 v2.0.4 // indirect
	// --- END feature:profiling ---
	// --- BEGIN feature:profiling lang:cpp ---
	github.com/google/pprof v0.0.0-20260709232956-b9395ee17fa0
	// --- END feature:profiling lang:cpp ---
	github.com/pmezard/go-difflib v1.0.1-0.20181226105442-5d4384ee4fb2 // indirect
	gopkg.in/yaml.v3 v3.0.1 // indirect
)

// --- BEGIN feature:profiling ---
tool github.com/felixge/pprofutils/v2/cmd/pprofutils

// --- END feature:profiling ---

// --- BEGIN feature:profiling lang:cpp ---
// Converts + symbolizes gperftools' legacy profile format against the bench
// binary's ELF symtab; the C++ capture path can't emit symbolized protos
// in-process the way Go/Rust do.
tool github.com/google/pprof

// --- END feature:profiling lang:cpp ---
