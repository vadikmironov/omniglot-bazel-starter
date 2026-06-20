"""Publishes Java JARs to Maven coordinates."""

load(
    "//tools/publish:publish_defs.bzl",
    "DEFAULT_MAVEN_GROUP",
    "artifactory_upload",
)

def java_binary_publish(
        name,
        binary_target,
        artifact_id,
        group_id = DEFAULT_MAVEN_GROUP,
        repo_name = None,
        classifier = "",
        visibility = None):
    """Publishes a fat JAR (java_binary's _deploy.jar) to Maven coordinates.

    Unlike binary_bundle_publish (which zips a launcher script plus the
    classpath JAR fan-out), this publishes the single self-contained
    _deploy.jar that Bazel synthesizes as an implicit output of every
    java_binary. The resulting artifact contains your bytecode plus all
    transitive dependency classes merged into one JAR with Main-Class set
    in the manifest (taken from the java_binary's main_class attribute).

    Consumers can run it directly with `java -jar <name>.jar` or depend on
    it as a Maven artifact. The JVM itself is NOT bundled — consumers still
    provide their own runtime.

    Must live in the same package as binary_target.

    Args:
        name: Target name (conventionally "publish").
        binary_target: Label of the java_binary target. Must be in the same
            package as this macro call (e.g., ":java_app").
        artifact_id: Maven artifact ID (e.g., "java-app").
        group_id: Maven group ID.
        repo_name: Repository name override. If None, PUBLISH_MODE selects
            maven_release_repo or maven_snapshot_repo, falling back to
            generic_repo. Fails if nothing is configured.
        classifier: Maven classifier (e.g., "all" to mark as fat JAR), empty
            if none. JVM bytecode is platform-independent so classifier is
            usually unnecessary.
        visibility: Bazel visibility.
    """

    # Strip the optional ":" prefix to get the bare target name; reject
    # cross-package references because the runfiles path below assumes the
    # _deploy.jar sits in this package.
    if binary_target.startswith("//"):
        fail("java_binary_publish requires binary_target in the same package; got: " + binary_target)
    target_name = binary_target.lstrip(":")

    deploy_jar_filename = target_name + "_deploy.jar"
    deploy_jar_target = ":" + deploy_jar_filename

    pkg = native.package_name()
    artifact_path = "_main/" + pkg + "/" + deploy_jar_filename

    artifactory_upload(
        name = name,
        artifact = deploy_jar_target,
        artifact_runfiles_path = artifact_path,
        mode = "maven",
        repo_name = repo_name,
        artifact_id = artifact_id,
        group_id = group_id,
        classifier = classifier,
        packaging = "jar",
        visibility = visibility,
    )

def java_publish(
        name,
        library_target,
        artifact_id,
        group_id = DEFAULT_MAVEN_GROUP,
        repo_name = None,
        jar_basename = None,
        visibility = None):
    """Publishes a Java library JAR to Maven coordinates.

    By default, assumes the target is a java_library and derives the JAR filename
    as lib<target_name>.jar. For java_binary targets, pass jar_basename explicitly
    (e.g., jar_basename = "my_app.jar").

    Args:
        name: Target name (conventionally "publish").
        library_target: Label of the java_library or java_binary target.
        artifact_id: Maven artifact ID (e.g., "java-lib").
        group_id: Maven group ID.
        repo_name: Repository name override. If None, PUBLISH_MODE selects
            maven_release_repo or maven_snapshot_repo, falling back to
            generic_repo. Fails if nothing is configured.
        jar_basename: Override the JAR filename in runfiles. If None, derived
            from library_target as "lib<target_name>.jar".
        visibility: Bazel visibility.
    """
    pkg = native.package_name()

    if jar_basename == None:
        # Parse target name from label
        if ":" in library_target:
            target_name = library_target.split(":")[-1]
        elif library_target.startswith("//"):
            target_name = library_target.split("/")[-1]
        else:
            target_name = library_target
        jar_basename = "lib" + target_name + ".jar"

    artifact_path = "_main/" + pkg + "/" + jar_basename

    artifactory_upload(
        name = name,
        artifact = library_target,
        artifact_runfiles_path = artifact_path,
        mode = "maven",
        repo_name = repo_name,
        artifact_id = artifact_id,
        group_id = group_id,
        packaging = "jar",
        visibility = visibility,
    )
