"""Publish orchestration engine for mint.

Builds a versioned publish plan from config + git state,
then executes it (dev from working tree, release from worktree with tagging).
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from mint.config import PublishConfig
from mint.git import (
    create_tag,
    delete_tag,
    get_git_commit,
    get_git_count,
    get_last_tag,
    parse_tag_version,
    push_tags,
    tag_version_string,
    validate_branch_exists,
)
from mint.label import label_to_image_publish_target, label_to_publish_target
from mint.scope import group_by_version_scope, resolve_scope
from mint.version import resolve_dev_version, resolve_release_version
from mint.worktree import secure_worktree

# --- Publish-target track selection -----------------------------------
# A mint run pushes to one or both of two distinct remote infras: a
# Maven/PyPI registry (artifact track) and an OCI image registry. These
# values are the choices for --include-pub-targets at the CLI and the
# matching `include` parameter on engine entry points. Mandatory choice
# (vs. an opt-out boolean pair) keeps the user's intent explicit on
# every invocation — both registries have non-trivial blast radius and
# different audit trails.

INCLUDE_ARTIFACTS = "artifacts"
INCLUDE_IMAGES = "images"
INCLUDE_ALL = "all"
INCLUDE_CHOICES = (INCLUDE_ARTIFACTS, INCLUDE_IMAGES, INCLUDE_ALL)


@dataclass(frozen=True)
class GroupPlan:
    """Resolved version info for one version group."""

    tag_prefix: str
    modules: list[str]
    raw_version: str
    formatted_version: str
    tag: str | None  # tag name for release, None for dev


@dataclass(frozen=True)
class PublishPlan:
    """Complete publish plan ready for execution."""

    mode: str
    branch: str | None
    groups: list[GroupPlan]


def build_plan(
    config: PublishConfig,
    mode: str,
    scope: str | None = None,
    branch: str | None = None,
    version_override: str | None = None,
    cwd: Path | None = None,
) -> PublishPlan:
    """Build a publish plan by resolving versions for all modules in scope.

    For each version group, queries git tags to determine the last published
    version, then computes the next version according to the schema.
    """
    modules = resolve_scope(config, scope)
    if not modules:
        return PublishPlan(mode=mode, branch=branch, groups=[])

    version_groups = group_by_version_scope(config, modules)
    _, schema = config.resolve_schema()

    groups = []
    for vg in version_groups:
        if version_override:
            raw_version = version_override
        else:
            last_tag = get_last_tag(prefix=vg.tag_prefix, cwd=cwd)
            last_version = parse_tag_version(last_tag, vg.tag_prefix) if last_tag else None
            git_count = get_git_count(from_ref=last_tag, cwd=cwd) if last_tag else get_git_count(cwd=cwd)

            if mode == "release":
                raw_version = resolve_release_version(schema, last_version, git_count=git_count)
            else:
                git_commit = get_git_commit(cwd=cwd)
                next_release = resolve_release_version(schema, last_version, git_count=git_count)
                raw_version = resolve_dev_version(schema, next_release, git_count, git_commit)

        formatted = config.format_version(raw_version)
        tag = tag_version_string(vg.tag_prefix, raw_version) if mode == "release" else None

        groups.append(
            GroupPlan(
                tag_prefix=vg.tag_prefix,
                modules=vg.modules,
                raw_version=raw_version,
                formatted_version=formatted,
                tag=tag,
            )
        )

    return PublishPlan(mode=mode, branch=branch, groups=groups)


def execute_plan(
    plan: PublishPlan,
    include: str,
    dry_run: bool = False,
    cwd: Path | None = None,
) -> None:
    """Execute a publish plan.

    Dev mode builds from the working tree. Release mode creates a worktree,
    tags locally, builds, then pushes tags only on full success.

    include is one of INCLUDE_ARTIFACTS / INCLUDE_IMAGES / INCLUDE_ALL
    and selects which target track(s) to invoke. Required (no default)
    so callers commit to an explicit choice — both registries have
    non-trivial blast radius.
    """
    _validate_include(include)
    if not plan.groups:
        print("Nothing to publish.")
        return

    print_plan(plan, include=include, cwd=cwd)
    if dry_run:
        return

    if plan.mode == "dev":
        _execute_dev(plan, include=include, cwd=cwd)
    else:
        _execute_release(plan, include=include, cwd=cwd)


def print_plan(
    plan: PublishPlan,
    include: str = INCLUDE_ALL,
    cwd: Path | None = None,
) -> None:
    """Print human-readable plan summary.

    For each module, prints the artifact target (:publish) and — when
    discovery finds it — the image target (:publish_image). Tracks
    deselected by `include` are annotated rather than omitted, so the
    dry-run output explains why a target that *would* run is being
    suppressed.

    `include` defaults to INCLUDE_ALL so this function remains usable
    in contexts (tests, ad-hoc inspection) that don't model the CLI's
    mandatory choice. The CLI itself always passes an explicit value
    via execute_plan.
    """
    _validate_include(include)
    do_artifact = include in (INCLUDE_ARTIFACTS, INCLUDE_ALL)
    do_image = include in (INCLUDE_IMAGES, INCLUDE_ALL)
    print(f"Publish plan ({plan.mode}):")
    if plan.branch:
        print(f"  Branch: {plan.branch}")
    print()
    for group in plan.groups:
        scope_label = group.tag_prefix or "(repo-wide)"
        print(f"  [{scope_label}] version={group.formatted_version}")
        if group.tag:
            print(f"    tag: {group.tag}")
        for module in group.modules:
            artifact_target = label_to_publish_target(module)
            artifact_suffix = "" if do_artifact else f" (skipped: --include-pub-targets={include})"
            print(f"    -> {artifact_target}{artifact_suffix}")
            image_target = label_to_image_publish_target(module)
            if _bazel_target_exists(image_target, cwd=cwd):
                image_suffix = "" if do_image else f" (skipped: --include-pub-targets={include})"
                print(f"    -> {image_target}{image_suffix}")
    print()


def _execute_dev(plan: PublishPlan, include: str, cwd: Path | None = None) -> None:
    """Execute dev mode: build and publish from working tree."""
    for group in plan.groups:
        for module in group.modules:
            _run_module_targets(
                module=module,
                version=group.formatted_version,
                mode=plan.mode,
                cwd=cwd,
                include=include,
            )


def _execute_release(plan: PublishPlan, include: str, cwd: Path | None = None) -> None:
    """Execute release mode: tag, build in worktree, push tags on success."""
    if plan.branch is None:
        raise ValueError("Release mode requires --branch")

    validate_branch_exists(plan.branch, cwd=cwd)

    all_tags = [g.tag for g in plan.groups if g.tag]

    with secure_worktree(plan.branch, cwd=cwd) as worktree:
        for tag in all_tags:
            create_tag(tag, cwd=worktree)

        try:
            for group in plan.groups:
                for module in group.modules:
                    _run_module_targets(
                        module=module,
                        version=group.formatted_version,
                        mode=plan.mode,
                        cwd=worktree,
                        include=include,
                    )
            push_tags(all_tags, cwd=worktree)
        except Exception:
            for tag in all_tags:
                delete_tag(tag, cwd=worktree)
            raise


def _run_module_targets(
    module: str,
    version: str,
    mode: str,
    cwd: Path | None,
    include: str,
) -> None:
    """Run :publish then :publish_image for one module, sequentially.

    Targets are run in stable order — artifact first, then image —
    matching the spec's "first failure aborts" guarantee: an image push
    never runs if the artifact upload that semantically precedes it
    fails. The image target is invoked only when bazel query confirms
    its existence in the BUILD graph (gazelle emits :publish_image only
    for binary kinds with a configured [image_bases] entry, so libraries
    and opted-out packages naturally fall through here).
    """
    if include in (INCLUDE_ARTIFACTS, INCLUDE_ALL):
        _run_publish(label_to_publish_target(module), version, mode, cwd=cwd)
    if include not in (INCLUDE_IMAGES, INCLUDE_ALL):
        return
    image_target = label_to_image_publish_target(module)
    if _bazel_target_exists(image_target, cwd=cwd):
        _run_publish(image_target, version, mode, cwd=cwd)


def _validate_include(include: str) -> None:
    """Reject unknown `include` values at API boundaries.

    argparse already enforces this at the CLI, but engine functions are
    also called directly from tests and would otherwise silently emit a
    plan that runs neither track. Failing fast with a typed error keeps
    the misuse mode obvious.
    """
    if include not in INCLUDE_CHOICES:
        raise ValueError(
            f"include must be one of {INCLUDE_CHOICES}; got {include!r}",
        )


def _bazel_target_exists(target: str, cwd: Path | None = None) -> bool:
    """Return True iff bazel query resolves the target to a rule.

    Used to discover :publish_image targets without mint having to
    replicate gazelle's emission rules. The query is cheap on the
    second+ invocation (analysis cache is warm). Any non-zero exit or
    empty stdout is treated as "not present" — if the BUILD file is
    actually broken, the artifact :publish run will surface the same
    error and abort, so we don't need to disambiguate here.
    """
    result = subprocess.run(
        ["bazel", "query", target],
        cwd=cwd,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def _run_publish(target: str, version: str, mode: str, cwd: Path | None = None) -> None:
    """Run a single publish target via bazel."""
    env = os.environ.copy()
    env["PUBLISH_VERSION"] = version
    env["PUBLISH_MODE"] = mode

    cmd = ["bazel", "run", "--config=publish", target]
    print(f"  Running: PUBLISH_VERSION={version} PUBLISH_MODE={mode} {' '.join(cmd)}")

    subprocess.run(cmd, check=True, cwd=cwd, env=env)
