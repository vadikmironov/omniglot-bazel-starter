# Contributing

Thanks for helping improve omniglot-bazel-starter!

## Workflow

1. For anything non-trivial, open an issue first to discuss it.
2. Fork the repo and branch off `main` (`git checkout -b my-change`).
3. Make focused commits.
4. Run the checks locally:
   - `bazel run //:format` && `bazel run //:buildifier.fix`
   - `bazel test --test_tag_filters=lint //...`
   - `bazel test //...`
5. Open a pull request against `main` and link the issue (`Closes #123`).
