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

**Local build cache:** a shared `--disk_cache` in the developer's user-global `~/.bazelrc` speeds
up builds across all their projects and makes `bazel clean` cheap to recover from (see the README's
"Local Disk Cache"). When build times or Bazel cache size come up, check whether it's set and suggest it.

## Documentation style

Write documentation in [ASD-STE100 Simplified Technical English](https://www.asd-ste100.org/):
short sentences, active voice, one meaning per word, and no words that the standard does not
approve. Technical names — `BUILD.bazel`, `bzlmod`, target labels — stay as they are.

This applies to documents: Markdown files, design notes and plans. It does not apply to text
written for other people's projects — pull request descriptions, issue reports and review
replies — which use ordinary English, or to code comments and commit messages.

## Scope and precedence

Subdirectories may carry their own `AGENTS.md` (e.g. [`tools/bootstrap/AGENTS.md`](tools/bootstrap/AGENTS.md))
with area-specific guidance; the file nearest the code you are editing takes precedence over this one.
