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


class SamplerUnsupportedError(ProfileError):
    """A bench flavor with no system-sampler support: batch runs skip the
    target with a note, a single-target run reports it as an error."""


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
    skipped = []
    ran = 0
    if sampler is not None and mode == MEM:
        raise ProfileError("--sampler applies to CPU benches only; memory capture is in-process")
    modes = [CPU, MEM] if mode is None else [mode]
    if sampler is not None:
        modes = [CPU]
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
            except SamplerUnsupportedError as err:
                ran -= 1
                skipped.append((label, str(err)))
            except ProfileError as err:
                failures.append((label, str(err)))
    print(f"\nprofiled {ran - len(failures)}/{ran} targets")
    for label, reason in skipped:
        print(f"  SKIPPED {label}: {reason}")
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
    # Fresh directory per run: several capture paths collect their inputs
    # by glob, so leftovers from renamed benches or a previously failed
    # run would be re-rendered as current data.
    if outdir.exists():
        shutil.rmtree(outdir)
    outdir.mkdir(parents=True)
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


# Bench flavors: how a CPU bench target's framework is driven. Keyed by
# rule kind; each language's bench framework has its own CLI and profile
# output shape, while everything downstream of the pprof file is shared.
# A kind listed here but without a flavor implementation below fails
# with "not yet supported" rather than "unsupported kind".
_BENCH_FLAVORS = {
    # --- BEGIN lang:rust ---
    "rust_binary": "criterion",
    # --- END lang:rust ---
    # --- BEGIN lang:go ---
    "go_test": "gotest",
    # --- END lang:go ---
    # --- BEGIN lang:cpp ---
    "cc_binary": "google_benchmark",
    # --- END lang:cpp ---
    # --- BEGIN lang:python ---
    "py_test": "pytest_benchmark",
    # --- END lang:python ---
    # --- BEGIN lang:java ---
    "java_binary": "jmh",
    # --- END lang:java ---
}


def _bench_flavor(label: str, cwd: Path) -> str:
    kind = _rule_kind(label, cwd)
    flavor = _BENCH_FLAVORS.get(kind)
    if flavor is None:
        supported = ", ".join(sorted(_BENCH_FLAVORS))
        raise ProfileError(f"{label} has unsupported bench kind {kind}; supported kinds: {supported}")
    return flavor


def _unsupported_flavor(flavor: str) -> ProfileError:
    return ProfileError(f"the {flavor} bench flavor is not yet supported by the runner")


def _run_cpu_profile(
    label: str,
    outdir: Path,
    cwd: Path,
    tools: spine.Tools,
    size: int | None,
    profile_seconds: int,
) -> None:
    flavor = _bench_flavor(label, cwd)
    # --- BEGIN lang:rust ---
    if flavor == "criterion":
        _run_cpu_profile_criterion(label, outdir, cwd, tools, size, profile_seconds)
        return
    # --- END lang:rust ---
    # --- BEGIN lang:go ---
    if flavor == "gotest":
        _run_cpu_profile_gotest(label, outdir, cwd, tools, size, profile_seconds)
        return
    # --- END lang:go ---
    # --- BEGIN lang:cpp ---
    if flavor == "google_benchmark":
        _run_cpu_profile_google_benchmark(label, outdir, cwd, tools, size, profile_seconds)
        return
    # --- END lang:cpp ---
    # --- BEGIN lang:python ---
    if flavor == "pytest_benchmark":
        _run_cpu_profile_pytest_benchmark(label, outdir, cwd, tools, size, profile_seconds)
        return
    # --- END lang:python ---
    # --- BEGIN lang:java ---
    if flavor == "jmh":
        _run_cpu_profile_jmh(label, outdir, cwd, tools, size, profile_seconds)
        return
    # --- END lang:java ---
    raise _unsupported_flavor(flavor)


# --- BEGIN lang:rust ---
def _run_cpu_profile_criterion(
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
        ["--", *_criterion_args(profile_seconds)],
        cwd,
        env,
        config="profile",
    )
    _render_criterion_profiles(label, criterion_home, outdir, tools)


def _criterion_args(profile_seconds: int | None) -> list[str]:
    if profile_seconds is None:
        return ["--bench"]
    return ["--bench", "--profile-time", str(profile_seconds)]


# --- END lang:rust ---


# --- BEGIN lang:go ---
def _run_cpu_profile_gotest(
    label: str,
    outdir: Path,
    cwd: Path,
    tools: spine.Tools,
    size: int | None,
    profile_seconds: int,
) -> None:
    pb = outdir / "profile.pb"
    _bazel_run(label, ["--", *_gotest_args(pb, profile_seconds)], cwd, _env(size), config="profile")
    _render_go_profile(label, pb, outdir, tools)


def _gotest_args(pb: Path | None, profile_seconds: int | None) -> list[str]:
    args = ["-test.run=^$", "-test.bench=."]
    if profile_seconds is not None:
        args.append(f"-test.benchtime={profile_seconds}s")
    if pb is not None:
        args.append(f"-test.cpuprofile={pb}")
    return args


def _render_go_profile(label: str, pb: Path, outdir: Path, tools: spine.Tools) -> None:
    if not pb.is_file():
        raise ProfileError(f"{label} did not write a CPU profile to {pb}")
    name = _target_name(label)
    folded = outdir / f"{name}.folded"
    svg = outdir / f"{name}.svg"
    spine.pprof_to_folded(tools, pb, folded)
    spine.folded_to_svg(tools, folded, svg, title=f"{label} (CPU)", countname="samples")
    _report(folded, svg, outdir / f"{name}.top.txt")


# --- END lang:go ---


# --- BEGIN lang:cpp ---
def _run_cpu_profile_google_benchmark(
    label: str,
    outdir: Path,
    cwd: Path,
    tools: spine.Tools,
    size: int | None,
    profile_seconds: int,
) -> None:
    raw = outdir / "profile.raw"
    env = _env(size, CPUPROF_OUT=str(raw))
    _bazel_run(label, ["--", *_google_benchmark_args(profile_seconds)], cwd, env, config="profile")
    _render_gperftools_cpu(label, raw, outdir, cwd, tools)


def _google_benchmark_args(profile_seconds: int | None) -> list[str]:
    if profile_seconds is None:
        return []
    return [f"--benchmark_min_time={profile_seconds}s"]


def _render_gperftools_cpu(label: str, raw: Path, outdir: Path, cwd: Path, tools: spine.Tools) -> None:
    if not raw.is_file():
        raise ProfileError(f"{label} did not write a CPU profile to {raw}")
    pb = outdir / "profile.pb"
    spine.gperftools_to_pb(tools, _built_binary(label, cwd), raw, pb)
    raw.unlink()
    name = _target_name(label)
    folded = outdir / f"{name}.folded"
    svg = outdir / f"{name}.svg"
    spine.pprof_to_folded(tools, pb, folded)
    spine.folded_to_svg(tools, folded, svg, title=f"{label} (CPU)", countname="samples")
    _report(folded, svg, outdir / f"{name}.top.txt")


# --- END lang:cpp ---


# --- BEGIN lang:python ---
def _run_cpu_profile_pytest_benchmark(
    label: str,
    outdir: Path,
    cwd: Path,
    tools: spine.Tools,
    size: int | None,
    profile_seconds: int,
) -> None:
    name = _target_name(label)
    folded = outdir / f"{name}.folded"
    env = _env(size, CPUPROF_OUT=str(folded))
    _bazel_run(label, ["--", *_pytest_benchmark_args(profile_seconds)], cwd, env, config="profile")
    if not folded.is_file():
        raise ProfileError(f"{label} did not write folded stacks to {folded}")
    svg = outdir / f"{name}.svg"
    spine.folded_to_svg(tools, folded, svg, title=f"{label} (CPU)", countname="us")
    _report(folded, svg, outdir / f"{name}.top.txt")


def _pytest_benchmark_args(profile_seconds: int | None) -> list[str]:
    # --benchmark-enable overrides the target's default --benchmark-disable
    # (its bazel-test smoke mode); max-time stretches the measurement loops
    # the in-process sampler observes.
    args = ["--benchmark-enable"]
    if profile_seconds is not None:
        args.append(f"--benchmark-max-time={profile_seconds}")
    return args


# --- END lang:python ---


# --- BEGIN lang:java ---
def _run_cpu_profile_jmh(
    label: str,
    outdir: Path,
    cwd: Path,
    tools: spine.Tools,
    size: int | None,
    profile_seconds: int,
) -> None:
    jfr_dir = outdir / "jfr"
    jfr_dir.mkdir(parents=True, exist_ok=True)
    _bazel_run(label, ["--", *_jmh_args(jfr_dir, profile_seconds)], cwd, _env(size), config="profile")
    recordings = sorted(jfr_dir.glob("*/profile.jfr"))
    if not recordings:
        raise ProfileError(f"{label} produced no JFR recordings under {jfr_dir}")
    for jfr in recordings:
        # jfr/<package>.<Class>.<bench>-<Mode>/profile.jfr
        parts = jfr.parent.name.split(".")
        bench_id = ".".join(parts[-2:]).rpartition("-")[0] or jfr.parent.name
        folded = outdir / f"{bench_id}.folded"
        svg = outdir / f"{bench_id}.svg"
        spine.jfr_to_folded(tools, jfr, folded, mode="cpu")
        spine.folded_to_svg(tools, folded, svg, title=f"{label} {bench_id} (CPU)", countname="samples")
        _report(folded, svg, outdir / f"{bench_id}.top.txt")
    shutil.rmtree(jfr_dir)


def _jmh_args(jfr_dir: Path, profile_seconds: int | None) -> list[str]:
    # One fork, one warmup, one long measurement iteration recorded by
    # JMH's JFR profiler (per-benchmark recordings under jfr_dir).
    seconds = 5 if profile_seconds is None else profile_seconds
    return [
        *("-f", "1", "-wi", "1", "-w", "1s", "-i", "1", "-r", f"{seconds}s"),
        *("-prof", f"jfr:dir={jfr_dir}"),
    ]


def _jmh_measure_args() -> list[str]:
    # A trimmed but honest dev-loop protocol (~8s per bench function);
    # publication-grade numbers want JMH's full defaults (multiple forks).
    return ["-f", "1", "-wi", "3", "-w", "1s", "-i", "5", "-r", "1s"]


# --- END lang:java ---


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
    flavor = _bench_flavor(label, cwd)
    # --- BEGIN lang:rust ---
    if flavor == "criterion":
        criterion_home = outdir / "criterion"
        env = _env(size, CRITERION_HOME=str(criterion_home))
        _perf_record_and_render(label, _criterion_args(profile_seconds), env, outdir, cwd, tools)
        _render_criterion_profiles(label, criterion_home, outdir, tools)
        return
    # --- END lang:rust ---
    # --- BEGIN lang:go ---
    if flavor == "gotest":
        pb = outdir / "profile.pb"
        _perf_record_and_render(label, _gotest_args(pb, profile_seconds), _env(size), outdir, cwd, tools)
        _render_go_profile(label, pb, outdir, tools)
        return
    # --- END lang:go ---
    # --- BEGIN lang:cpp ---
    if flavor == "google_benchmark":
        raw = outdir / "profile.raw"
        env = _env(size, CPUPROF_OUT=str(raw))
        _perf_record_and_render(label, _google_benchmark_args(profile_seconds), env, outdir, cwd, tools)
        _render_gperftools_cpu(label, raw, outdir, cwd, tools)
        return
    # --- END lang:cpp ---
    # --- BEGIN lang:python ---
    if flavor == "pytest_benchmark":
        raise SamplerUnsupportedError(
            "--sampler=perf is not supported for Python benches: perf sees interpreter frames, not Python functions"
        )
    # --- END lang:python ---
    # --- BEGIN lang:java ---
    if flavor == "jmh":
        raise SamplerUnsupportedError(
            "--sampler=perf is not supported for JMH benches: "
            "JIT frames need a perf map agent; use the in-process JFR capture"
        )
    # --- END lang:java ---
    raise _unsupported_flavor(flavor)


def _perf_record_and_render(
    label: str,
    bench_args: list[str],
    env: dict[str, str],
    outdir: Path,
    cwd: Path,
    tools: spine.Tools,
) -> None:
    binary = _built_binary(label, cwd)
    perf_data = outdir / "perf.data"
    cmd = ["perf", "record", "-F", "997", "-g", "-o", str(perf_data), "--", str(binary), *bench_args]
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


# --- BEGIN lang:rust ---
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


# --- END lang:rust ---


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
    # --- BEGIN lang:cpp ---
    if _rule_kind(label, cwd) == "cc_binary":
        # tcmalloc dumps gperftools' legacy format under a MEMPROF_OUT
        # prefix; symbolize + convert the last (live-heap) dump to pprof.
        prefix = outdir / "heap"
        env = _env(size, MEMPROF_OUT=str(prefix))
        _bazel_run(label, [], cwd, env, config="profile")
        dumps = sorted(outdir.glob("heap.*.heap"))
        if not dumps:
            raise ProfileError(f"{label} did not write heap dumps to {prefix}.*.heap")
        spine.gperftools_to_pb(tools, _built_binary(label, cwd), dumps[-1], pb)
        for dump in dumps:
            dump.unlink()
        _render_mem_profile(label, pb, outdir, tools)
        return
    # --- END lang:cpp ---
    # --- BEGIN lang:java ---
    if _rule_kind(label, cwd) == "java_binary":
        # The shim dumps a JFR recording of weighted allocation samples;
        # jfrconv renders it as collapsed stacks (bytes).
        jfr = outdir / "recording.jfr"
        env = _env(size, MEMPROF_OUT=str(jfr))
        _bazel_run(label, [], cwd, env, config="profile")
        if not jfr.is_file():
            raise ProfileError(f"{label} did not write a JFR recording to {jfr}")
        folded = outdir / "profile.folded"
        spine.jfr_to_folded(tools, jfr, folded, mode="alloc")
        jfr.unlink()
        _render_mem_folded(label, folded, outdir, tools)
        return
    # --- END lang:java ---
    # --- BEGIN lang:python ---
    if _rule_kind(label, cwd) == "py_binary":
        # The memray shim writes folded stacks (bytes) directly.
        folded = outdir / "profile.folded"
        env = _env(size, MEMPROF_OUT=str(folded))
        _bazel_run(label, [], cwd, env, config="profile")
        if not folded.is_file():
            raise ProfileError(f"{label} did not write folded stacks to {folded}")
        _render_mem_folded(label, folded, outdir, tools)
        return
    # --- END lang:python ---
    env = _env(size, MEMPROF_OUT=str(pb))
    _bazel_run(label, [], cwd, env, config="profile")
    if not pb.is_file():
        raise ProfileError(f"{label} did not write a heap profile to {pb}")
    _render_mem_profile(label, pb, outdir, tools)


def _render_mem_profile(label: str, pb: Path, outdir: Path, tools: spine.Tools) -> None:
    folded = outdir / "profile.folded"
    spine.pprof_to_folded(tools, pb, folded, trim_jemalloc=True)
    _render_mem_folded(label, folded, outdir, tools)


def _render_mem_folded(label: str, folded: Path, outdir: Path, tools: spine.Tools) -> None:
    svg = outdir / "flame.svg"
    spine.folded_to_svg(tools, folded, svg, title=f"{label} (heap)", countname="bytes")
    _report(folded, svg, outdir / "top.txt")


def _run_measure(label: str, cwd: Path, size: int | None) -> None:
    flavor = _bench_flavor(label, cwd)
    args: list[str] | None = None
    # --- BEGIN lang:rust ---
    if flavor == "criterion":
        args = _criterion_args(None)
    # --- END lang:rust ---
    # --- BEGIN lang:go ---
    if flavor == "gotest":
        args = _gotest_args(None, None)
    # --- END lang:go ---
    # --- BEGIN lang:cpp ---
    if flavor == "google_benchmark":
        args = _google_benchmark_args(None)
    # --- END lang:cpp ---
    # --- BEGIN lang:python ---
    if flavor == "pytest_benchmark":
        args = _pytest_benchmark_args(None)
    # --- END lang:python ---
    # --- BEGIN lang:java ---
    if flavor == "jmh":
        args = _jmh_measure_args()
    # --- END lang:java ---
    if args is None:
        raise _unsupported_flavor(flavor)
    _bazel_run(label, ["--", *args], cwd, _env(size), config=None)
    print("\nreminder: quote timings from --measure runs only; profile runs distort them")


def _report(folded: Path, svg: Path, top_path: Path) -> None:
    top = spine.top_n(folded)
    top_path.write_text(top, encoding="utf-8")
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


def _rule_kind(label: str, cwd: Path) -> str:
    cmd = ["bazel", "query", "--output=label_kind", label]
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ProfileError(f"bazel query failed:\n{result.stderr.strip()}")
    # "<kind> rule <label>"
    return result.stdout.split()[0]


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
