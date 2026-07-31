"""Tests for the runner's pure helpers.

Everything here avoids subprocess: the capture paths themselves are exercised
by running the profiler, but the argument builders below decide *how* each
bench framework is driven, and a silent change to one of them corrupts every
measurement it produces without failing anything. The artifact-layout helpers
are pinned for the same reason — `--view` rediscovers profiles by that layout.
"""

import os
import unittest
from pathlib import Path

from profiling import engine


class BenchArgsTest(unittest.TestCase):
    """The per-framework measurement protocol."""

    def test_criterion_profile_time_only_when_asked(self) -> None:
        self.assertEqual(engine._criterion_args(None), ["--bench"])
        self.assertEqual(engine._criterion_args(3), ["--bench", "--profile-time", "3"])

    def test_gotest_writes_a_cpuprofile_only_when_given_a_path(self) -> None:
        base = ["-test.run=^$", "-test.bench=."]
        self.assertEqual(engine._gotest_args(None, None), base)
        pb = Path("/tmp/profile.pb")
        self.assertEqual(
            engine._gotest_args(pb, 2),
            [*base, "-test.benchtime=2s", f"-test.cpuprofile={pb}"],
        )

    # --- BEGIN lang:cpp ---
    def test_google_benchmark_passes_min_time(self) -> None:
        self.assertEqual(engine._google_benchmark_args(None), [])
        self.assertEqual(engine._google_benchmark_args(4), ["--benchmark_min_time=4s"])

    # --- END lang:cpp ---

    def test_pytest_benchmark_always_re_enables_benchmarks(self) -> None:
        """The targets default to --benchmark-disable for their bazel-test smoke
        run, so the profiler has to turn them back on or it samples nothing."""
        self.assertEqual(engine._pytest_benchmark_args(None), ["--benchmark-enable"])
        self.assertIn("--benchmark-max-time=7", engine._pytest_benchmark_args(7))

    # --- BEGIN lang:java ---
    def test_jmh_profile_run_uses_one_fork_and_one_iteration(self) -> None:
        args = engine._jmh_args(Path("/tmp/jfr"), None)
        self.assertEqual(args[args.index("-f") + 1], "1")
        self.assertEqual(args[args.index("-i") + 1], "1")
        self.assertEqual(args[args.index("-r") + 1], "5s", "default profile length")
        self.assertIn("-prof", args)
        self.assertIn("jfr:dir=/tmp/jfr", args)
        self.assertEqual(engine._jmh_args(Path("/tmp/jfr"), 9)[args.index("-r") + 1], "9s")

    def test_jmh_measure_run_warms_up_and_repeats(self) -> None:
        """Measure mode is a different protocol from profile mode: profiling
        distorts timings, so measured numbers come from more iterations."""
        args = engine._jmh_measure_args()
        self.assertEqual(args[args.index("-wi") + 1], "3")
        self.assertEqual(args[args.index("-i") + 1], "5")
        self.assertNotIn("-prof", args)

    # --- END lang:java ---


class BenchFlavorTest(unittest.TestCase):
    """Which framework drives a bench target, keyed by its rule kind."""

    def flavor(self, kind: str) -> str:
        original = engine._rule_kind
        engine._rule_kind = lambda label, cwd: kind  # type: ignore[assignment]
        try:
            return engine._bench_flavor("//x:y", Path("."))
        finally:
            engine._rule_kind = original  # type: ignore[assignment]

    def test_each_language_maps_to_its_framework(self) -> None:
        for kind, expected in (
            ("rust_binary", "criterion"),
            ("go_test", "gotest"),
            # --- BEGIN lang:cpp ---
            ("cc_binary", "google_benchmark"),
            # --- END lang:cpp ---
            ("py_test", "pytest_benchmark"),
            # --- BEGIN lang:java ---
            ("java_binary", "jmh"),
            # --- END lang:java ---
        ):
            self.assertEqual(self.flavor(kind), expected, kind)

    def test_an_unknown_kind_lists_the_supported_ones(self) -> None:
        with self.assertRaises(engine.ProfileError) as caught:
            self.flavor("sh_binary")
        message = str(caught.exception)
        self.assertIn("sh_binary", message)
        for kind in engine._BENCH_FLAVORS:
            self.assertIn(kind, message, "the error should name what *is* supported")


class ArtifactLayoutTest(unittest.TestCase):
    """Where captures land — `--view` rediscovers profiles by this layout."""

    def test_target_name_from_a_label(self) -> None:
        self.assertEqual(engine._target_name("//modules/go_workloads:bench_matmul"), "bench_matmul")
        # A label without an explicit target names the package's last segment.
        self.assertEqual(engine._target_name("//modules/go_workloads"), "go_workloads")

    def test_outdir_flattens_the_package_path(self) -> None:
        out = engine._outdir(Path("/out"), "//modules/go_workloads:mem_string_churn", "mem")
        self.assertEqual(out, Path("/out/modules_go_workloads/mem_string_churn/mem"))

    def test_env_sets_workload_n_only_when_sized(self) -> None:
        self.assertNotIn("WORKLOAD_N", engine._env(None))
        self.assertEqual(engine._env(512)["WORKLOAD_N"], "512")
        # Extras ride along, and the ambient environment is preserved.
        self.assertEqual(engine._env(None, MEMPROF_OUT="/tmp/x")["MEMPROF_OUT"], "/tmp/x")
        self.assertEqual(engine._env(None).get("PATH"), os.environ.get("PATH"))


class BucketFileDiscoveryTest(unittest.TestCase):
    """The folded-per-bucket contract Java and Python capture through."""

    def setUp(self) -> None:
        self.tmp = Path(os.environ["TEST_TMPDIR"]) / self.id()
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.profile = self.tmp / "profile.folded"

    def test_no_bucket_files_means_no_table(self) -> None:
        self.assertIsNone(engine._take_bucket_files(self.profile))

    def test_bucket_files_are_joined_and_consumed(self) -> None:
        for bucket, value in (("alloc_space", 4000), ("inuse_space", 1000)):
            self.profile.with_name(f"profile.folded.{bucket}.folded").write_text(
                f"main;work {value}\n", encoding="utf-8"
            )
        table = engine._take_bucket_files(self.profile)
        assert table is not None
        self.assertEqual(table.types, ["alloc_space", "inuse_space"])
        self.assertEqual(dict(table.rows)["main;work"], [4000, 1000])
        # They are intermediates: the runner removes them once joined.
        self.assertEqual(list(self.tmp.glob("*.folded")), [])


if __name__ == "__main__":
    unittest.main()
