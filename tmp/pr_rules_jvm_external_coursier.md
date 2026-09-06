`COURSIER_CACHE` is set only on the pinned path in `coursier.bzl`, so a repin
spawns coursier without it. Coursier then derives its cache location from the
JVM's `user.home`, which on Linux comes from the passwd database and ignores
`$HOME`, while the Starlark side derives it from `$HOME` (or `$XDG_CACHE_HOME`).

Where the two disagree — `$HOME` on a network mount — coursier writes somewhere
Starlark does not expect, and the returned artifact paths cannot be relativized
against the cache, so the repin fails.

This backports the `coursier.bzl` half of upstream PR #1601, which adds
`get_coursier_environment()` and calls it on both paths. The patch drops when
that lands.

The PR's unit tests are left out: this repo does not run rules_jvm_external's
own suite, and they would add ~130 lines of patch surface with nothing
exercising them.

## Verifying

The failure only reproduces where `$HOME` and the passwd home disagree, so CI
cannot see it. On an affected machine this should now work without the
`COURSIER_CACHE` workaround:

```
REPIN=1 bazel run @omniglot-bazel-starter_maven_dependencies//:pin
```

Previously that needed:

```
bazel run --repo_env=REPIN=1 --repo_env=COURSIER_CACHE=<local dir> \
  @omniglot-bazel-starter_maven_dependencies//:pin
```

## Checked

buildifier, patch confirmed applied to the fetched repo, `bazel build --nobuild
--lockfile_mode=error //...`, Java build and tests, `MODULE.bazel.lock`
unchanged.
