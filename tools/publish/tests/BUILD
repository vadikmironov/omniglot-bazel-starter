load("@bazel_skylib//rules:build_test.bzl", "build_test")
load("@bazel_skylib//rules:write_file.bzl", "write_file")
load("@rules_python//python:defs.bzl", "py_test")
load("@rules_shell//shell:sh_test.bzl", "sh_test")
load("//tools/publish/lang:generic_publish_defs.bzl", "binary_bundle_publish", "library_archive_publish")
load("//tools/publish/lang:image_publish_defs.bzl", "image_publish")
load("//tools/publish/lang:java_publish_defs.bzl", "java_binary_publish", "java_publish")

# =========================================================================
# Tier 1a: Synthetic fixture build tests
#
# Verify each publish macro variant produces valid Bazel targets using
# minimal stub inputs. These are self-contained and survive bootstrapping.
# =========================================================================

write_file(
    name = "fake_binary",
    out = "fake_binary.sh",
    content = [
        "#!/bin/bash",
        "echo test",
    ],
    is_executable = True,
)

binary_bundle_publish(
    name = "test_binary_bundle_publish",
    artifact_id = "test-binary",
    binary_target = ":fake_binary",
)

genrule(
    name = "fake_library",
    outs = ["fake_library.a"],
    cmd = "touch $@",
)

library_archive_publish(
    name = "test_library_archive_publish",
    artifact_id = "test-library",
    library_target = ":fake_library",
)

genrule(
    name = "fake_java_lib",
    outs = ["libfake_java_lib.jar"],
    cmd = "touch $@",
)

java_publish(
    name = "test_java_publish",
    artifact_id = "test-java-lib",
    library_target = ":fake_java_lib",
)

# Stand-in for java_binary's implicit _deploy.jar output: the macro looks for
# a label named "<binary_target>_deploy.jar" in the current package, so any
# rule producing a file by that name satisfies the dependency.
genrule(
    name = "fake_java_app_deploy.jar",
    outs = ["fake_java_app_deploy.jar.out"],
    cmd = "touch $@",
)

java_binary_publish(
    name = "test_java_binary_publish",
    artifact_id = "test-java-app",
    binary_target = ":fake_java_app",
)

# image_publish produces a public sh_binary <name> that wraps an
# oci_push, alongside private _<name>_app_layer / _<name>_image /
# _<name>_image_linux / _<name>_push / _<name>_gen intermediates.
image_publish(
    name = "test_image_publish",
    artifact_id = "test-image",
    base = "@gcr_io_distroless_static",
    binary_target = ":fake_binary",
    entrypoint = ["/app/fake_binary.sh"],
    strip_prefix = package_name(),
)

# Java-shaped fixture: exercises the {runtime_args} placeholder + cmd.
image_publish(
    name = "test_image_publish_with_runtime_args",
    artifact_id = "test-image-args",
    base = "@gcr_io_distroless_static",
    binary_target = ":fake_binary",
    cmd = [
        "--config",
        "/etc/app.yaml",
    ],
    entrypoint = [
        "java",
        "{runtime_args}",
        "-jar",
        "/app/fake.jar",
    ],
    runtime_args = [
        "-Xmx2g",
        "-XX:+UseG1GC",
    ],
    strip_prefix = package_name(),
)

build_test(
    name = "publish_macros_build_test",
    targets = [
        ":test_binary_bundle_publish",
        ":test_library_archive_publish",
        ":test_java_publish",
        ":test_java_binary_publish",
        ":test_image_publish",
        ":test_image_publish_with_runtime_args",
    ],
)

# =========================================================================
# Tier 1b: Real module publish target build tests
#
# Verify the 10 standard module :publish targets (1 app + 1 lib per
# language) build successfully. Excludes _with_ext_dep variants and
# hybrid cpp_py_* modules as they test no new publish macro logic.
# =========================================================================

build_test(
    name = "module_publish_targets_build_test",
    targets = [
        "//modules/cpp_app:publish",
        "//modules/cpp_library:publish",
        "//modules/go_app:publish",
        "//modules/go_lib:publish",
        "//modules/java_app:publish",
        "//modules/java_lib:publish",
        "//modules/python_app:publish",
        "//modules/python_lib:publish",
        "//modules/rust_app:publish",
        "//modules/rust_lib:publish",
    ],
)

# Image companion: one :publish_image per binary kind (cc, go, java, py,
# rust). Validates that gazelle's per-kind formula produces a buildable
# image_publish call across all five mappings — strip_prefix variants,
# the java _deploy.jar reroute, and the py_binary venv layout that
# requires .bazelrc's venvs_use_declare_symlink=no.
build_test(
    name = "module_publish_image_targets_build_test",
    targets = [
        "//modules/cpp_app:publish_image",
        "//modules/go_app:publish_image",
        "//modules/java_app:publish_image",
        "//modules/python_app:publish_image",
        "//modules/rust_app:publish_image",
    ],
)

# =========================================================================
# Tier 2: Shell tests
# =========================================================================

sh_test(
    name = "credential_helper_test",
    size = "small",
    srcs = ["credential_helper_test.sh"],
    data = [
        "testlib.sh",
        "//tools/publish:credential-helper",
        "//tools/publish:netrc_lib.sh",
    ],
)

sh_test(
    name = "publish_artifact_test",
    size = "small",
    srcs = ["publish_artifact_test.sh"],
    data = [
        "testlib.sh",
        "//tools/publish:publish_artifact.sh",
        "//tools/publish:repackage_wheel.py",
    ],
)

py_test(
    name = "test_repackage_wheel",
    size = "small",
    srcs = ["test_repackage_wheel.py"],
    data = ["//tools/publish:repackage_wheel.py"],
)

py_test(
    name = "test_docker_login_helper",
    size = "small",
    srcs = ["test_docker_login_helper.py"],
    data = ["//tools/publish:docker_login_helper.py"],
)
