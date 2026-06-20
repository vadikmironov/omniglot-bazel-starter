"""Command-line interface for mint."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from mint.config import load_config
from mint.engine import INCLUDE_CHOICES, build_plan, execute_plan


def main() -> None:
    """Entry point for the mint CLI."""
    parser = argparse.ArgumentParser(
        prog="mint",
        description="Monorepo publish orchestrator — version management and coordinated publishing.",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["dev", "release"],
        help="dev: publish from working tree; release: tag and publish from clean worktree",
    )
    parser.add_argument(
        "--scope",
        default=None,
        help="component set name, Bazel label (//...), or omit for everything",
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="branch to release from (required for release mode)",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="explicit version override (skips git tag resolution)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print resolved plan without building or publishing",
    )
    parser.add_argument(
        "--include-pub-targets",
        required=True,
        choices=list(INCLUDE_CHOICES),
        help=(
            "which publish-target track(s) to invoke per module: "
            "'artifacts' (Maven/PyPI :publish only), 'images' "
            "(OCI :publish_image only), or 'all' (both, artifact-first). "
            "Required — both registries have non-trivial blast radius "
            "and different audit trails, so the choice is explicit."
        ),
    )

    args = parser.parse_args()

    if args.mode == "release" and not args.branch:
        parser.error("--branch is required for release mode")

    # Guard against argument injection: reject values that look like flags.
    for name in ("branch", "scope", "version"):
        value = getattr(args, name)
        if value is not None and value.startswith("-"):
            parser.error(f"--{name} value must not start with '-': {value}")

    workspace = _resolve_workspace()
    config_path = workspace / ".publish.toml"

    if not config_path.exists():
        print(f"ERROR: {config_path} not found", file=sys.stderr)
        sys.exit(1)

    config = load_config(config_path)

    plan = build_plan(
        config=config,
        mode=args.mode,
        scope=args.scope,
        branch=args.branch,
        version_override=args.version,
        cwd=workspace,
    )

    execute_plan(
        plan,
        include=args.include_pub_targets,
        dry_run=args.dry_run,
        cwd=workspace,
    )


def _resolve_workspace() -> Path:
    """Determine the workspace root.

    When run via ``bazel run``, uses BUILD_WORKSPACE_DIRECTORY.
    Otherwise falls back to walking up from CWD looking for .publish.toml.
    """
    workspace_dir = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
    if workspace_dir:
        return Path(workspace_dir)
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".publish.toml").exists():
            return parent
    return cwd
