# AGENTS.md

Vendor-neutral entry point for AI coding agents working in this repository.
The authoritative, detailed guidance lives in **[CLAUDE.md](CLAUDE.md)** — read it first.

## Essentials

A Bazel (bzlmod) polyglot monorepo — Python, Rust, C++, Java, Go. Drive everything through Bazel:

```bash
bazel build //...                          # build all targets
bazel test //...                           # run tests (excludes lint)
bazel run //:format                        # format sources (all languages)
bazel run //:buildifier.fix                # format Bazel/Starlark files
bazel test --test_tag_filters=lint //...   # run lint
```

[CLAUDE.md](CLAUDE.md) is the full reference: build/test/lint, toolchain selection and debugging,
dependency regeneration, publishing, and the **Post Development Checks** to run before committing.

## Scope and precedence

Subdirectories may carry their own `AGENTS.md` (e.g. [`tools/bootstrap/AGENTS.md`](tools/bootstrap/AGENTS.md))
with area-specific guidance; the file nearest the code you are editing takes precedence over this one.
