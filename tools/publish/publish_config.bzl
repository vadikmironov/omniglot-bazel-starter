"""Custom rule that reads Starlark build settings and generates a shell config file.

This bridges .bazelrc flags (build-time) to the publish wrapper scripts (run-time).
The generated config file is sourced by the wrapper, with env vars taking precedence.
"""

load("@bazel_skylib//rules:common_settings.bzl", "BuildSettingInfo")

def _validate_no_single_quotes(value, name):
    if "'" in value:
        fail("{} build setting must not contain single quotes (got: {})".format(name, value))

def _publish_config_impl(ctx):
    url = ctx.attr._url[BuildSettingInfo].value
    docker_url = ctx.attr._docker_url[BuildSettingInfo].value
    platform = ctx.attr._platform[BuildSettingInfo].value
    owner = ctx.attr._owner[BuildSettingInfo].value
    maven_release_repo = ctx.attr._maven_release_repo[BuildSettingInfo].value
    maven_snapshot_repo = ctx.attr._maven_snapshot_repo[BuildSettingInfo].value
    pypi_repo = ctx.attr._pypi_repo[BuildSettingInfo].value
    docker_repo = ctx.attr._docker_repo[BuildSettingInfo].value
    generic_repo = ctx.attr._generic_repo[BuildSettingInfo].value

    for name, value in [
        ("publish_url", url),
        ("publish_docker_url", docker_url),
        ("publish_platform", platform),
        ("publish_owner", owner),
        ("publish_maven_release_repo", maven_release_repo),
        ("publish_maven_snapshot_repo", maven_snapshot_repo),
        ("publish_pypi_repo", pypi_repo),
        ("publish_docker_repo", docker_repo),
        ("publish_generic_repo", generic_repo),
    ]:
        _validate_no_single_quotes(value, name)

    config = ctx.actions.declare_file(ctx.attr.name + ".sh")
    ctx.actions.write(
        output = config,
        content = "\n".join([
            "# Auto-generated publish config from .bazelrc build settings.",
            "# Do not edit — configure via --config=publish or user.bazelrc.",
            "PUBLISH_URL_DEFAULT='" + url + "'",
            "PUBLISH_DOCKER_URL_DEFAULT='" + docker_url + "'",
            "PUBLISH_PLATFORM_DEFAULT='" + platform + "'",
            "PUBLISH_OWNER_DEFAULT='" + owner + "'",
            "PUBLISH_MAVEN_RELEASE_REPO_DEFAULT='" + maven_release_repo + "'",
            "PUBLISH_MAVEN_SNAPSHOT_REPO_DEFAULT='" + maven_snapshot_repo + "'",
            "PUBLISH_PYPI_REPO_DEFAULT='" + pypi_repo + "'",
            "PUBLISH_DOCKER_REPO_DEFAULT='" + docker_repo + "'",
            "PUBLISH_GENERIC_REPO_DEFAULT='" + generic_repo + "'",
            "",
        ]),
    )
    return [DefaultInfo(files = depset([config]))]

publish_config = rule(
    implementation = _publish_config_impl,
    attrs = {
        "_url": attr.label(default = "//tools/publish:url"),
        "_docker_url": attr.label(default = "//tools/publish:docker_url"),
        "_platform": attr.label(default = "//tools/publish:platform"),
        "_owner": attr.label(default = "//tools/publish:owner"),
        "_maven_release_repo": attr.label(default = "//tools/publish:maven_release_repo"),
        "_maven_snapshot_repo": attr.label(default = "//tools/publish:maven_snapshot_repo"),
        "_pypi_repo": attr.label(default = "//tools/publish:pypi_repo"),
        "_docker_repo": attr.label(default = "//tools/publish:docker_repo"),
        "_generic_repo": attr.label(default = "//tools/publish:generic_repo"),
    },
)
