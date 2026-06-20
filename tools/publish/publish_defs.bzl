"""Core publish infrastructure for uploading artifacts to Artifactory/Gitea/Nexus.

Provides:
  - artifactory_upload:   Low-level wrapper — generates a publish script for any artifact
  - DEFAULT_MAVEN_GROUP:  Shared Maven group ID constant

Language-specific macros that build on artifactory_upload are in
//tools/publish/lang/ (java, python, generic archive).

Version is supplied at runtime via PUBLISH_VERSION env var (set by mint or manually).
"""

load("@bazel_skylib//rules:write_file.bzl", "write_file")
load("@rules_shell//shell:sh_binary.bzl", "sh_binary")

DEFAULT_MAVEN_GROUP = "com.monorepo.test"

_VALID_MODES = ["maven", "pypi", "generic"]

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_no_single_quotes(value, name):
    """Fail if value contains single quotes that would break generated shell scripts."""
    if "'" in value:
        fail("{} must not contain single quotes (got: {})".format(name, value))

def _repo_name_lines(mode, repo_name):
    """Generate REPO_NAME resolution lines for the wrapper script.

    When repo_name is set explicitly in a macro, it is used directly (no
    snapshot/release logic, no fallback chain).

    Otherwise, resolution depends on the mode:
      maven:   PUBLISH_MODE selects snapshot or release repo → generic fallback → fail
      pypi:    pypi repo → generic fallback → fail
      generic: generic repo → fail

    Each step tries the runtime env var first, then the .bazelrc default
    (sourced from publish_config.sh as *_DEFAULT vars).
    """
    if repo_name:
        return ["REPO_NAME='" + repo_name + "'"]

    if mode == "maven":
        return [
            "if [[ \"${PUBLISH_MODE:-}\" == \"dev\" ]]; then",
            "    REPO_NAME=\"${PUBLISH_MAVEN_SNAPSHOT_REPO:-${PUBLISH_MAVEN_SNAPSHOT_REPO_DEFAULT:-}}\"",
            "else",
            "    REPO_NAME=\"${PUBLISH_MAVEN_RELEASE_REPO:-${PUBLISH_MAVEN_RELEASE_REPO_DEFAULT:-}}\"",
            "fi",
            "if [[ -z \"${REPO_NAME}\" ]]; then",
            "    REPO_NAME=\"${PUBLISH_GENERIC_REPO:-${PUBLISH_GENERIC_REPO_DEFAULT:-}}\"",
            "fi",
            "if [[ -z \"${REPO_NAME}\" ]]; then",
            "    echo 'ERROR: No Maven repository configured.' >&2",
            "    echo 'Configure in .bazelrc (or user.bazelrc):' >&2",
            "    echo '  build:publish --//tools/publish:maven_release_repo=<name>' >&2",
            "    echo '  build:publish --//tools/publish:maven_snapshot_repo=<name>' >&2",
            "    exit 1",
            "fi",
        ]
    elif mode == "pypi":
        return [
            "REPO_NAME=\"${PUBLISH_PYPI_REPO:-${PUBLISH_PYPI_REPO_DEFAULT:-}}\"",
            "if [[ -z \"${REPO_NAME}\" ]]; then",
            "    REPO_NAME=\"${PUBLISH_GENERIC_REPO:-${PUBLISH_GENERIC_REPO_DEFAULT:-}}\"",
            "fi",
            "if [[ -z \"${REPO_NAME}\" ]]; then",
            "    echo 'ERROR: No PyPI repository configured.' >&2",
            "    echo 'Configure in .bazelrc (or user.bazelrc):' >&2",
            "    echo '  build:publish --//tools/publish:pypi_repo=<name>' >&2",
            "    exit 1",
            "fi",
        ]
    else:
        return [
            "REPO_NAME=\"${PUBLISH_GENERIC_REPO:-${PUBLISH_GENERIC_REPO_DEFAULT:-}}\"",
            "if [[ -z \"${REPO_NAME}\" ]]; then",
            "    echo 'ERROR: No generic repository configured.' >&2",
            "    echo 'Configure in .bazelrc (or user.bazelrc):' >&2",
            "    echo '  build:publish --//tools/publish:generic_repo=<name>' >&2",
            "    exit 1",
            "fi",
        ]

def _wrapper_script_content(
        mode,
        repo_name,
        artifact_runfiles_path,
        group_id,
        artifact_id,
        classifier,
        packaging):
    """Build the content lines for the generated wrapper script."""
    return [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Locate runfiles directory",
        "RUNFILES=\"${BASH_SOURCE[0]}.runfiles\"",
        "if [[ ! -d \"${RUNFILES}\" ]]; then",
        "    RUNFILES=\"${0}.runfiles\"",
        "fi",
        "",
        "# Source publish config generated from .bazelrc build settings",
        "source \"${RUNFILES}/_main/tools/publish/publish_config.sh\"",
        "",
        "# Apply configuration: env vars override .bazelrc defaults",
        "export PUBLISH_URL=\"${PUBLISH_URL:-${PUBLISH_URL_DEFAULT:-}}\"",
        "export PUBLISH_PLATFORM=\"${PUBLISH_PLATFORM:-${PUBLISH_PLATFORM_DEFAULT:-artifactory}}\"",
        "export PUBLISH_OWNER=\"${PUBLISH_OWNER:-${PUBLISH_OWNER_DEFAULT:-}}\"",
        "",
        "if [[ -z \"${PUBLISH_URL}\" ]]; then",
        "    echo 'ERROR: No publish URL configured.' >&2",
        "    echo 'Set PUBLISH_URL env var or configure --config=publish in .bazelrc' >&2",
        "    echo 'See tools/publish/README.md for setup instructions.' >&2",
        "    exit 1",
        "fi",
        "",
        "if [[ -z \"${PUBLISH_VERSION:-}\" ]]; then",
        "    echo 'ERROR: PUBLISH_VERSION is required.' >&2",
        "    echo 'Use mint: bazel run //tools/publish:mint -- --mode dev' >&2",
        "    echo 'Or set directly: PUBLISH_VERSION=1.0.0 bazel run --config=publish ...' >&2",
        "    exit 1",
        "fi",
        "",
        "# Resolve repo name: explicit > mode env/flag > generic fallback > fail",
    ] + _repo_name_lines(mode, repo_name) + [
        "",
        "exec \"${RUNFILES}/_main/tools/publish/publish_artifact.sh\" \\",
        "    '" + mode + "' \"${REPO_NAME}\" \\",
        "    \"${RUNFILES}/" + artifact_runfiles_path + "\" \\",
        "    '" + group_id + "' '" + artifact_id + "' '" + classifier + "' '" + packaging + "'",
    ]

# ---------------------------------------------------------------------------
# Core macro
# ---------------------------------------------------------------------------

def artifactory_upload(
        name,
        artifact,
        artifact_runfiles_path,
        mode,
        artifact_id,
        repo_name = None,
        group_id = DEFAULT_MAVEN_GROUP,
        classifier = "",
        packaging = "zip",
        visibility = None):
    """Creates a runnable publish target that uploads an artifact.

    Requires PUBLISH_VERSION env var at runtime (set by mint or manually).

    Args:
        name: Target name (conventionally "publish").
        artifact: Label of the artifact to upload (appears in data/runfiles).
        artifact_runfiles_path: Runfiles path to the artifact file.
        mode: Upload mode — "maven", "pypi", or "generic".
        artifact_id: Maven artifact ID or generic package name.
        repo_name: Repository name on the server. If None, resolved at runtime
            based on mode and PUBLISH_MODE (snapshot/release for Maven),
            with fallback to generic_repo. Fails if nothing is configured.
        group_id: Maven group ID.
        classifier: Maven classifier (e.g., "linux-x86_64"), empty if none.
        packaging: File type/extension (e.g., "jar", "zip", "whl").
        visibility: Bazel visibility.
    """
    if mode not in _VALID_MODES:
        fail("Invalid mode '{}'. Supported modes: {}".format(mode, ", ".join(_VALID_MODES)))

    # Validate strings embedded in generated shell scripts
    _validate_no_single_quotes(mode, "mode")
    if repo_name:
        _validate_no_single_quotes(repo_name, "repo_name")
    _validate_no_single_quotes(artifact_id, "artifact_id")
    _validate_no_single_quotes(group_id, "group_id")
    _validate_no_single_quotes(classifier, "classifier")
    _validate_no_single_quotes(packaging, "packaging")

    script_content = _wrapper_script_content(
        mode = mode,
        repo_name = repo_name,
        artifact_runfiles_path = artifact_runfiles_path,
        group_id = group_id,
        artifact_id = artifact_id,
        classifier = classifier,
        packaging = packaging,
    )

    gen = "_" + name + "_gen"
    write_file(
        name = gen,
        out = name + ".sh",
        content = script_content,
        is_executable = True,
        visibility = ["//visibility:private"],
    )
    data_deps = [
        artifact,
        "//tools/publish:publish_artifact.sh",
        "//tools/publish:publish_config",
    ]
    if mode == "pypi":
        data_deps.append("//tools/publish:repackage_wheel.py")

    sh_binary(
        name = name,
        srcs = [":" + gen],
        data = data_deps,
        visibility = visibility,
    )
