"""Java test suite macro for creating multiple test targets from source files.

This module provides a macro that creates individual test targets for each test
source file, enabling better parallelization when running tests. It supports
both JUnit 4 and JUnit 5 test runners.

This implementation is derived from the rules_jvm project:
https://github.com/bazel-contrib/rules_jvm/blob/main/java/private/java_test_suite.bzl
https://github.com/bazel-contrib/rules_jvm/blob/main/java/private/create_jvm_test_suite.bzl
"""

load("@rules_java//java:java_test.bzl", "java_test")
load("//tools/java/testing:junit5_support.bzl", "java_junit5_test")

def _get_test_class(package, src):
    """Computes the fully qualified test class name from package and source file.

    Args:
        package: The Java package name.
        src: The source file path (e.g., "src/test/java/com/example/MyTest.java").

    Returns:
        The fully qualified class name (e.g., "com.example.MyTest").
    """
    class_name = src.split("/")[-1].replace(".java", "")
    if package:
        return package + "." + class_name
    return class_name

def _infer_package_from_path(src):
    """Attempts to infer the Java package from the source file path.

    Looks for common Java source directory patterns like "src/test/java/" or
    "src/main/java/" and extracts the package path from there.

    Args:
        src: The source file path.

    Returns:
        The inferred package name, or None if it cannot be determined.
    """
    java_markers = ["src/test/java/", "src/main/java/", "java/"]
    for marker in java_markers:
        if marker in src:
            # Extract path after marker, remove filename, convert to package
            package_path = src.split(marker)[-1]
            package_path = "/".join(package_path.split("/")[:-1])
            if package_path:
                return package_path.replace("/", ".")
    return None

def java_test_suite(
        name,
        srcs,
        package = None,
        runner = "junit5",
        deps = [],
        runtime_deps = [],
        size = None,
        tags = [],
        visibility = None,
        **kwargs):
    """Creates a test suite with individual test targets for each source file.

    This macro generates a separate test target for each source file in `srcs`,
    enabling better parallelization when running tests on remote build execution
    (RBE) or locally. All individual tests are aggregated into a test_suite.

    Args:
        name: The name of the test suite target.
        srcs: List of test source files. Each file will become a separate test target.
        package: The Java package name for the test classes. If not specified,
            it will be inferred from the source file paths (looking for patterns
            like "src/test/java/com/example/...").
        runner: The test runner to use. Either "junit5" (default) or "junit4".
        deps: Compile-time dependencies for the tests. For JUnit 5, the JUnit
            dependencies are automatically included.
        runtime_deps: Runtime dependencies for the tests.
        size: The test size (small, medium, large, enormous).
        tags: Tags to apply to individual test targets.
        visibility: Visibility of the test suite.
        **kwargs: Additional arguments passed to each test target
            (e.g., data, jvm_flags, env).

    Example:
        ```
        load("//tools/java/testing:java_test_suite.bzl", "java_test_suite")

        java_test_suite(
            name = "all_tests",
            srcs = glob(["src/test/java/**/*Test.java"]),
            package = "com.example.myapp",
            deps = [":myapp_lib"],
        )
        ```

        This creates individual test targets like `:_all_tests_MyServiceTest`,
        `:_all_tests_UtilsTest`, etc., and an `:all_tests` suite that runs them all.
    """
    if runner == "junit5":
        test_fn = java_junit5_test
    elif runner == "junit4":
        test_fn = java_test
    else:
        fail("Unknown runner '{}'. Must be 'junit5' or 'junit4'.".format(runner))

    test_names = []

    for src in srcs:
        # Derive test name from filename, prefixed with suite name for
        # consistent naming (individual tests are implementation details
        # of the suite and use the private _ prefix).
        class_name = src.split("/")[-1].replace(".java", "")
        test_name = "_{}_{}".format(name, class_name)

        # Compute the fully qualified test class name
        effective_package = package
        if not effective_package:
            effective_package = _infer_package_from_path(src)

        test_class = _get_test_class(effective_package, src)

        # Build the test target
        test_kwargs = dict(kwargs)
        if size:
            test_kwargs["size"] = size
        if tags:
            test_kwargs["tags"] = tags

        test_fn(
            name = test_name,
            srcs = [src],
            test_class = test_class,
            deps = deps,
            runtime_deps = runtime_deps,
            **test_kwargs
        )

        test_names.append(":" + test_name)

    # Create a test suite that includes all individual tests
    native.test_suite(
        name = name,
        tests = test_names,
        tags = tags,
        visibility = visibility,
    )
