# Draft: bazel-lib PR to drop the bundled jq toolchain

**Write the body yourself.** Raw material below.

Patch: `tmp/aspect_bazel_lib_drop_bundled_jq.patch` (applies to v2.22.5)

Depends on the jq.bzl PR landing and being released, since it moves the
dependency to a version carrying Windows arm64.

## Suggested title

Drop the bundled jq toolchain in favour of jq.bzl

## What is duplicated today

`lib/jq.bzl` is already a re-export:

```python
"""Re-export of https://registry.bazel.build/modules/jq.bzl to avoid breaking change."""
load("@jq.bzl//jq:jq.bzl", _jq = "jq")
```

That rule resolves `@jq.bzl//jq/toolchain`'s type, not
`@aspect_bazel_lib//lib:jq_toolchain_type`. So the toolchain in
`lib/private/jq_toolchain.bzl` is no longer what any `jq()` target uses, while
still being registered for every platform in its own `JQ_PLATFORMS` table.

Two tables, one of them unused by the rule and older: it pins jq 1.7 and has no
Windows arm64 entry.

## What that costs

On a Windows arm64 host, toolchain resolution fails in the generated repo:

```
ERROR: While resolving toolchains for target
@@aspect_bazel_lib++toolchains+jq_toolchains/BUILD.bazel:9:19
```

The failure surfaces on whatever target happened to pull bazel-lib in -- an
`oci` image push, for us -- so it reads as unrelated to jq. GitHub's Windows
arm64 runners are free for public repositories now, so this is reachable on
ordinary CI.

## The change

- delete `lib/private/jq_toolchain.bzl` and its `bzl_library`
- drop `register_jq_toolchains` and the `jq` tag class from the toolchains
  extension
- remove `jq_toolchain_type` and the repos it needed from `MODULE.bazel`
- move `jq.bzl` to 0.6.1

## Breaking change, stated plainly

`@aspect_bazel_lib//lib:jq_toolchain_type` is public API and this removes it.
Consumers referencing it directly should move to `@jq.bzl//jq/toolchain`. One
reference inside this repository, in `e2e/api_entries`, is updated here.

v3 has already removed jq from this repository, so this is bringing 2.x in line
rather than proposing a new direction. If 2.x is closed to breaking changes, the
narrower alternative is to add a `windows_arm64` entry and jq 1.8.2 to the
existing table, leaving the duplication in place. That patch is smaller but
keeps two sources of truth.
