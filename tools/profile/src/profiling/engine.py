"""Discovery and orchestration: bazel query for tagged targets, bazel run for
capture, then the shared rendering spine over the captured profiles."""

import os
import shutil
import subprocess
from pathlib import Path

from profiling import spine
from profiling.spine import ProfileError

CPU = "cpu"
MEM = "mem"

_TAGS = {CPU: "profiling-cpu", MEM: "profiling-mem"}


def list_targets(*, scope: str, cwd: Path, mode: str | None) -> None:
    for m in [CPU, MEM] if mode is None else [mode]:
        labels = _discover(_TAGS[m], scope, cwd)
        print(f"{_TAGS[m]}:")
        for label in labels:
            print(f"  {label}")
        if not labels:
            print("  (none)")


def run_all(
    *,
    scope: str,
    mode: str | None,
    out_root: Path,
    cwd: Path,
    size: int | None,
    profile_seconds: int,
    sampler: str | None = None,
) -> None:
    failures = []
    ran = 0
    modes = [CPU, MEM] if mode is None else [mode]
    if sampler is not None:
        modes = [CPU] if CPU in modes else []
    for m in modes:
        for label in _discover(_TAGS[m], scope, cwd):
            ran += 1
            try:
                run_one(
                    label=label,
                    mode=m,
                    measure=False,
                    out_root=out_root,
                    cwd=cwd,
                    size=size,
                    profile_seconds=profile_seconds,
                    sampler=sampler,
                )
            except ProfileError as err:
                failures.append((label, str(err)))
    print(f"\nprofiled {ran - len(failures)}/{ran} targets")
    if failures:
        for label, err in failures:
            print(f"  FAILED {label}: {err}")
        raise ProfileError("some targets failed")


def run_one(
    *,
    label: str,
    mode: str | None,
    measure: bool,
    out_root: Path,
    cwd: Path,
    size: int | None,
    profile_seconds: int,
    sampler: str | None = None,
) -> None:
    actual = _infer_mode(label, cwd)
    if mode is not None and mode != actual:
        raise ProfileError(f"{label} is tagged {_TAGS[actual]}, not {_TAGS[mode]}")

    if measure:
        if actual == MEM:
            raise ProfileError("--measure applies to CPU benches only; memory workloads run once")
        if sampler is not None:
            raise ProfileError("--measure and --sampler are mutually exclusive")
        _run_measure(label, cwd, size)
        return

    if sampler is not None and actual == MEM:
        raise ProfileError("--sampler applies to CPU benches only; memory capture is in-process")

    outdir = _outdir(out_root, label, actual)
    outdir.mkdir(parents=True, exist_ok=True)
    tools = spine.resolve_tools()
    if actual == CPU and sampler is not None:
        _run_cpu_profile_perf(label, outdir, cwd, tools, size, profile_seconds)
    elif actual == CPU:
        _run_cpu_profile(label, outdir, cwd, tools, size, profile_seconds)
    else:
        _run_mem_profile(label, outdir, cwd, tools, size)


def view(*, target: str | None, out_root: Path, cwd: Path) -> None:
    """Open flamelens on a .folded file or on a target's rendered artifacts."""
    if target is None:
        raise ProfileError("--view needs a target label or a .folded file")
    path = Path(target)
    if not path.is_file():
        candidates = []
        for mode in [CPU, MEM]:
            candidates += sorted(_outdir(out_root, target, mode).glob("*.folded"))
        if not candidates:
            raise ProfileError(f"no folded stacks for {target}; profile it first")
        path = max(candidates, key=lambda p: p.stat().st_mtime)
    tools = spine.resolve_tools()
    spine.view(tools, path)


def _run_cpu_profile(
    label: str,
    outdir: Path,
    cwd: Path,
    tools: spine.Tools,
    size: int | None,
    profile_seconds: int,
) -> None:
    criterion_home = outdir / "criterion"
    env = _env(size, CRITERION_HOME=str(criterion_home))
    _bazel_run(
        label,
        ["--", "--bench", "--profile-time", str(profile_seconds)],
        cwd,
        env,
        config="profile",
    )
    _render_criterion_profiles(label, criterion_home, outdir, tools)


def _run_cpu_profile_perf(
    label: str,
    outdir: Path,
    cwd: Path,
    tools: spine.Tools,
    size: int | None,
    profile_seconds: int,
) -> None:
    """Sample the bench binary with the host `perf` (non-hermetic opt-in).

    perf wraps the built binary directly — wrapping `bazel run` would profile
    the bazel client. One recording covers every bench function in the target;
    the in-process profiler still runs, so its per-function view is rendered
    alongside as `<bench>.{folded,svg}` next to the `-perf` artifacts.
    """
    _check_perf_available()
    binary = _built_binary(label, cwd)
    criterion_home = outdir / "criterion"
    env = _env(size, CRITERION_HOME=str(criterion_home))
    perf_data = outdir / "perf.data"
    cmd = [
        "perf",
        "record",
        "-F",
        "997",
        "-g",
        "-o",
        str(perf_data),
        "--",
        str(binary),
        "--bench",
        "--profile-time",
        str(profile_seconds),
    ]
    result = subprocess.run(cmd, cwd=cwd, env=env, check=False)
    if result.returncode != 0:
        raise ProfileError(f"perf record failed with exit code {result.returncode}")

    name = _target_name(label)
    folded = outdir / f"{name}-perf.folded"
    svg = outdir / f"{name}-perf.svg"
    spine.perf_to_folded(tools, perf_data, folded)
    spine.folded_to_svg(tools, folded, svg, title=f"{label} (CPU, perf)", countname="samples")
    _report(folded, svg, outdir / f"{name}-perf.top.txt")
    perf_data.unlink(missing_ok=True)
    _render_criterion_profiles(label, criterion_home, outdir, tools)


def _render_criterion_profiles(label: str, criterion_home: Path, outdir: Path, tools: spine.Tools) -> None:
    profiles = sorted(criterion_home.glob("**/profile/profile.pb"))
    if not profiles:
        raise ProfileError(f"{label} produced no profile.pb under {criterion_home}")
    for pb in profiles:
        # criterion/<group>[/<function>]/profile/profile.pb
        bench_id = "-".join(pb.relative_to(criterion_home).parts[:-2])
        folded = outdir / f"{bench_id}.folded"
        svg = outdir / f"{bench_id}.svg"
        spine.pprof_to_folded(tools, pb, folded)
        spine.folded_to_svg(tools, folded, svg, title=f"{label} {bench_id} (CPU)", countname="samples")
        _report(folded, svg, outdir / f"{bench_id}.top.txt")


def _check_perf_available() -> None:
    if shutil.which("perf") is None:
        raise ProfileError(
            "perf not found on PATH; the system sampler is non-hermetic — "
            "install it via your distribution's linux-tools package"
        )
    paranoid = Path("/proc/sys/kernel/perf_event_paranoid")
    try:
        level = int(paranoid.read_text().strip())
    except (OSError, ValueError):
        return
    if level > 2:
        raise ProfileError(
            f"kernel.perf_event_paranoid={level} blocks unprivileged sampling; "
            "lower it, e.g. sudo sysctl kernel.perf_event_paranoid=2"
        )


def _built_binary(label: str, cwd: Path) -> Path:
    """Build the target and return its output binary path (workspace-relative)."""
    build = subprocess.run(["bazel", "build", "--config=profile", label], cwd=cwd, check=False)
    if build.returncode != 0:
        raise ProfileError(f"bazel build {label} failed with exit code {build.returncode}")
    files = _bazel_cquery_files(label, cwd)
    if len(files) != 1:
        raise ProfileError(f"{label} produced {len(files)} output files; expected a single binary")
    return cwd / files[0]


def _bazel_cquery_files(label: str, cwd: Path) -> list[str]:
    cmd = ["bazel", "cquery", "--config=profile", "--output=files", label]
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ProfileError(f"bazel cquery failed:\n{result.stderr.strip()}")
    return [line for line in result.stdout.splitlines() if line]


def _run_mem_profile(
    label: str,
    outdir: Path,
    cwd: Path,
    tools: spine.Tools,
    size: int | None,
) -> None:
    pb = outdir / "profile.pb"
    env = _env(size, MEMPROF_OUT=str(pb))
    _bazel_run(label, [], cwd, env, config="profile")

    if not pb.is_file():
        raise ProfileError(f"{label} did not write a heap profile to {pb}")
    folded = outdir / "profile.folded"
    svg = outdir / "flame.svg"
    spine.pprof_to_folded(tools, pb, folded, trim_jemalloc=True)
    spine.folded_to_svg(tools, folded, svg, title=f"{label} (heap)", countname="bytes")
    _report(folded, svg, outdir / "top.txt")


def _run_measure(label: str, cwd: Path, size: int | None) -> None:
    _bazel_run(label, ["--", "--bench"], cwd, _env(size), config=None)
    print("\nreminder: quote timings from --measure runs only; profile runs distort them")


def _report(folded: Path, svg: Path, top_path: Path) -> None:
    top = spine.top_n(folded)
    top_path.write_text(top)
    print(f"\n{svg}")
    print(top, end="")


def _discover(tag: str, scope: str, cwd: Path) -> list[str]:
    result = _bazel_query(f'attr(tags, "{tag}", {scope})', cwd)
    return [line for line in result.splitlines() if line]


def _infer_mode(label: str, cwd: Path) -> str:
    for mode, tag in _TAGS.items():
        if _discover(tag, label, cwd):
            return mode
    raise ProfileError(f"{label} is not tagged {_TAGS[CPU]} or {_TAGS[MEM]}")


def _bazel_query(query: str, cwd: Path) -> str:
    cmd = ["bazel", "query", "--output=label", query]
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ProfileError(f"bazel query failed:\n{result.stderr.strip()}")
    return result.stdout


def _bazel_run(
    label: str,
    args: list[str],
    cwd: Path,
    env: dict[str, str],
    config: str | None,
) -> None:
    cmd = ["bazel", "run"]
    if config:
        cmd.append(f"--config={config}")
    else:
        cmd += ["-c", "opt"]
    cmd.append(label)
    cmd += args
    result = subprocess.run(cmd, cwd=cwd, env=env, check=False)
    if result.returncode != 0:
        raise ProfileError(f"bazel run {label} failed with exit code {result.returncode}")


def _env(size: int | None, **extra: str) -> dict[str, str]:
    env = {**os.environ, **extra}
    if size is not None:
        env["WORKLOAD_N"] = str(size)
    return env


def _target_name(label: str) -> str:
    pkg, _, name = label.replace("@", "").lstrip("/").partition(":")
    return name or pkg.rsplit("/", 1)[-1]


def _outdir(out_root: Path, label: str, mode: str) -> Path:
    pkg, _, _ = label.replace("@", "").lstrip("/").partition(":")
    return out_root / pkg.replace("/", "_") / _target_name(label) / mode
