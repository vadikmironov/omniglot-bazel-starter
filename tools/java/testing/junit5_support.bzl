"""JUnit Platform testing support for Bazel.

This module provides a macro for running JUnit Jupiter tests using the
JUnit Platform ConsoleLauncher. It wraps the standard java_test rule and
automatically configures JUnit dependencies. Supports both JUnit 5.x and
JUnit 6.x (Platform 1.x and 2.x).
"""

load("@rules_java//java:java_test.bzl", "java_test")
load("//tools/java:package_defs.bzl", "junit5_build_deps", "junit5_runtime_deps")

def java_junit5_test(name, test_class = None, deps = [], runtime_deps = [], **kwargs):
    """Runs a JUnit 5 test class using the ConsoleLauncher.

    This macro wraps java_test to execute JUnit 5 tests via the JUnit Platform
    ConsoleLauncher. JUnit 5 compile and runtime dependencies are automatically
    included, so you only need to specify your own test dependencies.

    Args:
        name: The name of the test target.
        test_class: Fully qualified name of the test class to run.
            Defaults to the target name if not specified.
        deps: Compile-time dependencies for the test. JUnit 5 API dependencies
            (junit-jupiter-api, junit-jupiter-engine) are automatically added.
        runtime_deps: Runtime dependencies for the test. JUnit 5 platform
            dependencies (junit-platform-console, junit-platform-launcher,
            junit-platform-reporting) are automatically added.
        **kwargs: Additional arguments passed to the underlying java_test rule
            (e.g., srcs, size, tags, data, jvm_flags, visibility).

    Example:
        ```
        load("//tools/java/testing:junit5_support.bzl", "java_junit5_test")

        java_junit5_test(
            name = "MyServiceTest",
            srcs = ["MyServiceTest.java"],
            test_class = "com.example.MyServiceTest",
            deps = [":my_service_lib"],
        )
        ```
    """
    java_test(
        name = name,
        main_class = "org.junit.platform.console.ConsoleLauncher",
        use_testrunner = False,
        args = [
            # JUnit 6+ requires 'execute' subcommand; options follow the subcommand
            "execute",
            "--select-class=" + (test_class or name),
            "--fail-if-no-tests",
        ],
        deps = deps + junit5_build_deps(),
        runtime_deps = runtime_deps + junit5_runtime_deps(),
        **kwargs
    )
