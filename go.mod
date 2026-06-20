module omniglot-bazel-starter

go 1.25.0

require (
	github.com/bazelbuild/bazel-gazelle v0.51.3
	github.com/stretchr/testify v1.11.1
)

require (
	github.com/bazel-contrib/bazel-gazelle/v2 v2.0.0-2 // indirect
	github.com/bazelbuild/buildtools v0.0.0-20250930140053-2eb4fccefb52 // indirect
	golang.org/x/mod v0.23.0 // indirect
	golang.org/x/sys v0.46.0 // indirect
	golang.org/x/tools/go/vcs v0.1.0-deprecated // indirect
)

// --- BEGIN exclude ---
require golang.org/x/net v0.56.0

// --- END exclude ---

require (
	github.com/BurntSushi/toml v1.6.0
	github.com/davecgh/go-spew v1.1.1 // indirect
	github.com/pmezard/go-difflib v1.0.0 // indirect
	gopkg.in/yaml.v3 v3.0.1 // indirect
)
