"""Shared capture shim for the CPU benches: when CPUPROF_OUT is set, the
whole pytest session runs under pyinstrument and its call tree is written
there as folded stacks (microsecond weights) for the //tools/profile spine.
Without CPUPROF_OUT the benches run unprofiled."""

import os

_profiler = None


def pytest_sessionstart(session):
    del session
    global _profiler
    if os.environ.get("CPUPROF_OUT"):
        # pytest-benchmark blanks sys profile hooks around every timed
        # section (PauseInstrumentation), which both hides the bench loops
        # from pyinstrument and crashes restoring its C-level profiler
        # state. Profiled runs are never measurement runs, so neutralize
        # the pauser and sample the real loops.
        from pytest_benchmark import fixture

        fixture.PauseInstrumentation.__enter__ = lambda self: None
        fixture.PauseInstrumentation.__exit__ = lambda self, *exc: None

        from pyinstrument import Profiler

        _profiler = Profiler(interval=0.001)
        _profiler.start()


def pytest_sessionfinish(session, exitstatus):
    del session, exitstatus
    if _profiler is None:
        return
    profile_session = _profiler.stop()
    _write_folded(profile_session, os.environ["CPUPROF_OUT"])


def _write_folded(profile_session, path):
    """Render pyinstrument's frame tree as folded stacks, weighting each
    stack by its self-time in whole microseconds."""
    from pyinstrument.session import Session

    assert isinstance(profile_session, Session)
    root = profile_session.root_frame()
    stacks = {}

    def walk(frame, ancestry):
        if frame.is_synthetic:
            # [self] and friends: fold their weight into the parent stack.
            stack = ancestry
        else:
            name = f"{frame.class_name}.{frame.function}" if frame.class_name else frame.function
            stack = (*ancestry, name)
        weight = int(frame.total_self_time * 1e6)
        if weight > 0 and stack:
            stacks[stack] = stacks.get(stack, 0) + weight
        for child in frame.children:
            walk(child, stack)

    if root is not None:
        walk(root, ())
    with open(path, "w", encoding="utf-8") as out:
        for stack, weight in stacks.items():
            out.write(";".join(stack) + f" {weight}\n")
