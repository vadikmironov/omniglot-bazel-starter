# Plan: pkgconf in the Bazel Central Registry

This plan has two phases. Phase 1 adds pkgconf to the Bazel Central Registry
(BCR). Phase 2 adds a repository that starts the version updates.

## Background

The `cmake()` and `make()` rules of rules_foreign_cc need a pkg-config
toolchain. On Windows, that toolchain builds pkg-config against an external
glib. Only one Windows glib binary exists. GNOME made it in 2010, and it is for
x64 only. Windows ARM64 thus has no pkg-config, and no `cmake()` target builds
there.

pkgconf has no external dependencies. It has 22 C files in `libpkgconf` and 4
files in `cli`. It compiles with `cc_binary` on each platform that the Bazel C++
toolchain supports. The build is in `//tools/cpp/foreign_cc` in this repository.
It is correct on Linux, macOS, Windows x64 and Windows ARM64.

## Phase 1: the BCR module

### Method

Use the overlay method. BCR gets the source archive from the pkgconf project.
BCR then adds our `BUILD.bazel` file to that archive. The overlay files stay in
the registry, in the directory of the module version.

The modules `sqlite3`, `zlib`, `curl` and `openssl` use this method. They are C
libraries, and their sources have no Bazel support. openssl is the closest
example. It has 50 overlay files, and it tests on `windows_arm64`.

Do not make a different module that gets pkgconf. That method needs a
repository, a release pipeline, and a version number that is not the same as
the pkgconf version number.

### Files to write

Put these files in `modules/pkgconf/<version>/` in the registry:

| File | Content |
| --- | --- |
| `source.json` | The URL of the pkgconf archive, its integrity hash, the prefix to remove, and one hash for each overlay file |
| `MODULE.bazel` | The module declaration and the `rules_cc` dependency |
| `presubmit.yml` | The platforms and the Bazel versions to test |
| `overlay/BUILD.bazel` | The build file. Copy it from `//tools/cpp/foreign_cc:pkgconf.BUILD` |
| `overlay/sample/` | A small module that a user can build. BCR tests it |

### Module declaration

```starlark
module(
    name = "pkgconf",
    version = "<version>",
    compatibility_level = 1,
    bazel_compatibility = [">=7.2.1"],
)
```

The overlay method needs Bazel 7.2.1 or later. The modules `sqlite3`, `curl`
and `openssl` all declare this limit.

Set `compatibility_level` to 1. pkgconf is a program, and no other program
links to it. Thus there is no ABI that can break.

### Changes to the build file

The build file is correct, but it needs three changes:

1. Take the version number from the module version. Do not write the number
   `3.0.6` in the file.
2. Add `alias(name = "pkgconf")` at the root of the module. The BCR guide asks
   for a target that has the name of the module. This alias makes the short
   label `@pkgconf` operate.
3. Add notes that tell how we made the build file and `config.h`. The BCR guide
   asks for these notes when a module has a large overlay.

Do not add a dependency on rules_foreign_cc. A BCR module can use only modules
that BCR already contains. Keep the `native_tool_toolchain` adapter in this
repository.

### Test configuration

Use the two-part configuration of the `sqlite3` module in `presubmit.yml`:

- A `tasks:` part that builds the module targets on each platform.
- A `bcr_test_module:` part that builds and tests the sample module.

Test on these platforms:

```
ubuntu2004, ubuntu2004_arm64, ubuntu2404, macos, macos_arm64,
windows, windows_arm64
```

Test with these Bazel versions:

```
7.x, 8.x, 9.x, rolling
```

Keep `7.x`. rules_foreign_cc is the user that this work helps. Its
`.bazelversion` file contains 7.4.1, and BCR tests it only with `7.x`. If
pkgconf does not support Bazel 7, rules_foreign_cc cannot use it.

Keep `windows_arm64`. It is the platform that this work makes possible. The
openssl module shows that BCR supports this platform.

### Validation of the binary

The tests must do more than a build. They must show that the binary operates
correctly:

- `pkgconf --version` gives the correct version.
- `pkgconf --cflags --libs` gives the correct flags for a test `.pc` file.
- `pkgconf --exists` gives a result that is not zero for a package that does
  not exist.
- `pkgconf --modversion` gives the version from the `.pc` file.

Also examine the dynamic dependencies of the binary. On Linux and macOS, the
binary must have no unexpected shared libraries. On Windows, the imports must
be system DLLs and `advapi32`. This test finds a change that adds a dependency
on the host. A test of this type found an obsolete libtinfo5 dependency in this
repository.

### Steps to submit

1. Run `tools/add_module.py` one time and answer the questions. The script
   writes a JSON file. Keep this file for Phase 2.
2. The script makes the module directory and calculates each hash.
3. Make a pull request to `bazelbuild/bazel-central-registry`.
4. A BCR maintainer must approve the pull request, because the module is new
   and has no maintainer.
5. A BCR maintainer must also start the CI, because you are a new contributor.
6. After the merge, you become the maintainer of the module.

The name `pkgconf` is the name of the upstream project. The BCR guide refuses
names that are too general, but it permits a name that the developer community
knows.

### Change to this repository

In `tools/cpp/foreign_cc/foreign_cc_tools.MODULE.bazel`, replace the
`http_archive` and `pkgconf.BUILD` with a `bazel_dep` on the new module. Keep
the `native_tool_toolchain` adapter. The behaviour does not change, and this
repository becomes smaller.

## Phase 2: the repository that starts the updates

### Purpose

The pkgconf project makes a new release approximately four times each year.
Phase 2 makes the update automatic. It also tests each new version before that
version goes to BCR.

### Content of the repository

The repository is small. It contains:

- `VERSION` — the pkgconf version and the hash of its archive.
- `overlay/` — the same files that Phase 1 put in the registry. This repository
  keeps the correct copy.
- `pkgconf.json` — the file that `tools/add_module.py` wrote in Phase 1.
- A workflow that builds and tests pkgconf on each platform.
- A workflow that makes the BCR pull request.

### How the update operates

1. Renovate examines the releases of `pkgconf/pkgconf`.
2. Renovate makes a pull request that changes `VERSION` and the hash.
3. The CI of this repository builds and tests the new version. It uses a
   `windows-11-arm` runner, and also Linux, macOS and Windows x64.
4. A person examines the results and merges the pull request.
5. A workflow starts. It gets a copy of your fork of the registry. It runs
   `tools/add_module.py --input=pkgconf.json` with the new version. The script
   writes the new module directory and calculates the hashes.
6. The workflow makes a pull request to `bazelbuild/bazel-central-registry`.

The script `tools/add_module.py` asks no questions when you give it the
`--input` option. A workflow can thus run it.

### Result

Each new version gets a test on real hardware before BCR receives it. This is
important, because a BCR version is permanent.

## Open questions

1. Must the repository of Phase 2 be private or public? A public repository
   lets other persons see the test results. A private repository is sufficient
   for the automatic operation.
2. Do you want to move the module to the `bazel-contrib` organization later?
   This decision is not urgent.

## Risk

A BCR module version is permanent. You cannot change a version after the merge;
you can only add a new version. If the build file has an error, a maintainer
must examine the correction.

The build file in this repository needed two corrections after the first
version. Only the tests on real Windows hardware found them. Phase 2 decreases
this risk, because it tests each new version before the submission.
