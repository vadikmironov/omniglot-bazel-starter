"""Command-line interface for the profiling runner.

Invoked as ``bazel run //tools/profile -- [TARGET] [flags]``. Targets are
discovered by tag: ``profiling-cpu`` marks criterion benches, ``profiling-mem``
marks one-shot memory workload binaries.
"""

import argparse
import os
import sys
from pathlib import Path

from profiling import engine


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.sampler:
        sys.exit("--sampler is not yet implemented; only in-process capture is available")

    workspace = _resolve_workspace()
    out_root = args.out or workspace / "profile-out"

    try:
        if args.list:
            engine.list_targets(scope=args.scope, cwd=workspace, mode=_mode(args))
        elif args.view:
            engine.view(target=args.target, out_root=out_root, cwd=workspace)
        elif args.all:
            engine.run_all(
                scope=args.scope,
                mode=_mode(args),
                out_root=out_root,
                cwd=workspace,
                size=args.size,
                profile_seconds=args.profile_seconds,
            )
        elif args.target:
            engine.run_one(
                label=args.target,
                mode=_mode(args),
                measure=args.measure,
                out_root=out_root,
                cwd=workspace,
                size=args.size,
                profile_seconds=args.profile_seconds,
            )
        else:
            parser.error("a target label is required (or use --list / --all)")
    except engine.ProfileError as err:
        sys.exit(f"error: {err}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="profile",
        description="Profile tagged workload targets and render flamegraphs.",
        epilog=("Benchmark timings must only be quoted from --measure runs; profile runs are not measurement runs."),
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Bazel label of a tagged workload target (with --view: a .folded file also works)",
    )
    parser.add_argument("--all", action="store_true", help="profile every discovered target")
    parser.add_argument("--list", action="store_true", help="list discovered workload targets")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--cpu", action="store_true", help="restrict to profiling-cpu targets")
    mode.add_argument("--mem", action="store_true", help="restrict to profiling-mem targets")
    parser.add_argument(
        "--measure",
        action="store_true",
        help="run the bench unprofiled for real timings (CPU targets only)",
    )
    parser.add_argument(
        "--view",
        action="store_true",
        help="open the target's folded stacks (or a given .folded file) in flamelens",
    )
    parser.add_argument("--scope", default="//...", help="target pattern for discovery")
    parser.add_argument("--size", type=int, help="workload size (exported as WORKLOAD_N)")
    parser.add_argument(
        "--profile-seconds",
        type=int,
        default=5,
        metavar="S",
        help="per-bench profiling duration for CPU targets (default: 5)",
    )
    parser.add_argument("--out", type=Path, help="artifact directory (default: <workspace>/profile-out)")
    parser.add_argument("--sampler", help="reserved for the external system sampler")
    return parser


def _mode(args: argparse.Namespace) -> str | None:
    if args.cpu:
        return engine.CPU
    if args.mem:
        return engine.MEM
    return None


def _resolve_workspace() -> Path:
    """Workspace root: BUILD_WORKSPACE_DIRECTORY under bazel run, else walk up."""
    workspace_dir = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
    if workspace_dir:
        return Path(workspace_dir)
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / "MODULE.bazel").exists():
            return parent
    return cwd
