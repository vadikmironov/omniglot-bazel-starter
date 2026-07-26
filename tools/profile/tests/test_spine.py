"""End-to-end tests for the rendering spine.

These drive the *real* pb2folded binary over real captured profiles rather
than stubbing it: the seam most likely to rot is the one between the
converter's output format and the Python that parses it, and a mock would
agree with itself forever. Fixtures under testdata/ are genuine one-shot
workload dumps, one per pprof heap shape the repo produces:

  go_heap_4type.pb    runtime/pprof — alloc_{objects,space}, inuse_{objects,space}
  cpp_heap_2type.pb   gperftools with nothing freed — objects, space
"""

import os
import unittest
from pathlib import Path

from profiling import spine

TESTDATA = Path(__file__).parent / "testdata"


def fixture(name: str) -> Path:
    return TESTDATA / name


def write_meta(directory: Path, **fields: int | str) -> Path:
    path = directory / "profile.pb.meta"
    path.write_text("".join(f"{key}={value}\n" for key, value in fields.items()), encoding="utf-8")
    return path


def write_folded(path: Path, stacks: dict[str, int]) -> Path:
    path.write_text("".join(f"{stack} {value}\n" for stack, value in stacks.items()), encoding="utf-8")
    return path


class SpineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tools = spine.resolve_tools()
        self.tmp = Path(os.environ["TEST_TMPDIR"]) / self.id()
        self.tmp.mkdir(parents=True, exist_ok=True)

    def render(self, pb: Path) -> spine.BucketTable:
        table = self.tmp / "buckets.tsv"
        spine.pprof_to_table(self.tools, pb, table)
        return spine.bucket_table(table)

    def test_go_heap_renders_four_buckets_folded_stacks_and_an_svg(self) -> None:
        """The whole memory path over a Go profile: table, report, fold, SVG."""
        meta = spine.read_meta(write_meta(self.tmp, vmrss_bytes=75_157_504, sample_rate_bytes=32_768))
        assert meta is not None
        self.assertEqual(meta.sample_rate_bytes, 32_768)

        table = self.render(fixture("go_heap_4type.pb"))
        self.assertEqual(table.types, ["alloc_objects", "alloc_space", "inuse_objects", "inuse_space"])

        report = spine.bucket_report(table, meta)
        # Grow is split across two samples (Go tags each with its size class),
        # so this also pins that the report sums them rather than showing one.
        self.assertRegex(report, r"68711\s+71932421\s+68711\s+71932421\s+\S*go_workloads\.Grow")
        self.assertIn("turnover     (alloc_space / inuse_space)        1.00x", report)
        self.assertIn("mean live", report)
        # Sampled capture must advertise its error bar, never bare digits.
        self.assertRegex(report, r"precision.*sampled @ 32,768 B.*live samples, ±\d+%")

        folded = self.tmp / "profile.folded"
        spine.pprof_to_folded(self.tools, fixture("go_heap_4type.pb"), folded, select="inuse_space,space", unit="bytes")
        top = spine.top_n(folded)
        self.assertIn("go_workloads.Grow", top)
        self.assertIn("71932421", top)

        svg = self.tmp / "flame.svg"
        spine.folded_to_svg(self.tools, folded, svg, title="test (heap, live)", countname="bytes")
        self.assertIn("go_workloads.Grow", svg.read_text(encoding="utf-8"))

    def test_cpp_two_type_heap_fills_all_four_buckets(self) -> None:
        """gperftools emits `objects`/`space` only when nothing was freed — which
        means alloc equals inuse, so both halves are populated from them."""
        table = self.render(fixture("cpp_heap_2type.pb"))
        self.assertEqual(table.types, ["objects", "space"])

        report = spine.bucket_report(table, spine.read_meta(write_meta(self.tmp, sample_rate_bytes=0)))
        self.assertRegex(report, r"65537\s+68681728\s+65537\s+68681728\s+.*__libcpp_allocate")
        self.assertIn("turnover     (alloc_space / inuse_space)        1.00x", report)
        self.assertIn("freed        (alloc_objects - inuse_objects)    0", report)
        self.assertIn("mean live    (inuse_space / inuse_objects)      1,048 B (1.0 KiB)", report)
        # tcmalloc records every allocation; nothing here is extrapolated.
        self.assertIn("precision    (every allocation tracked)         exact", report)
        self.assertNotIn("±", report)

    def test_a_lone_bucket_is_not_inflated_into_four(self) -> None:
        """One measurable column must not imply the rest: absent buckets read
        as a dash, and no ratio is computed against their implicit zero."""
        table = spine.folded_to_table(
            {"inuse_space": write_folded(self.tmp / "live.folded", {"main;grow": 68_171_581})}
        )
        self.assertEqual(table.types, ["inuse_space"])

        report = spine.bucket_report(table, None)
        for absent in ("alloc_objects", "alloc_space", "inuse_objects"):
            self.assertIsNone(table.column(absent))
        self.assertIn("turnover     (alloc_space / inuse_space)        —", report)
        self.assertIn("mean alloc   (alloc_space / alloc_objects)      —", report)
        self.assertIn("mean live    (inuse_space / inuse_objects)      —", report)
        self.assertIn("freed        (alloc_objects - inuse_objects)    —", report)
        self.assertIn("live / RSS   (inuse_space / VmRSS)              —", report)
        self.assertNotIn("0.00x", report)
        # The one real column still renders.
        self.assertRegex(report, r"68171581\s+.*grow")

    def test_selecting_a_bucket_the_profile_lacks_fails_loudly(self) -> None:
        """gperftools' 2-type shape carries objects/space and no alloc_space;
        ask for it and the run must stop rather than silently folding whatever
        sits at index 0."""
        target = fixture("cpp_heap_2type.pb")
        # Guard against the fixture going missing: pb2folded would then fail to
        # open it and raise for the wrong reason, passing this test vacuously.
        self.assertTrue(target.is_file())
        with self.assertRaises(spine.ProfileError) as caught:
            spine.pprof_to_folded(
                self.tools,
                target,
                self.tmp / "out.folded",
                select="alloc_space",
                unit="bytes",
            )
        self.assertIn("pb2folded", str(caught.exception))

    def test_folded_files_join_into_one_bucket_table(self) -> None:
        """Java and Python never produce a pprof, but both emit folded stacks —
        so one file per bucket joins into the same table pb2folded yields."""
        sources = {
            "alloc_objects": write_folded(self.tmp / "a.folded", {"main;work": 40, "main;setup": 2}),
            "alloc_space": write_folded(self.tmp / "b.folded", {"main;work": 4000, "main;setup": 200}),
            "inuse_objects": write_folded(self.tmp / "c.folded", {"main;work": 10}),
            "inuse_space": write_folded(self.tmp / "d.folded", {"main;work": 1000}),
        }
        table = spine.folded_to_table(sources)
        self.assertEqual(table.types, list(spine.BUCKETS))
        self.assertEqual(dict(table.rows)["main;work"], [40, 4000, 10, 1000])
        # A stack absent from the live files must read zero there, not vanish.
        self.assertEqual(dict(table.rows)["main;setup"], [2, 200, 0, 0])

        report = spine.bucket_report(table, spine.read_meta(write_meta(self.tmp, precision="exact")))
        self.assertIn("turnover     (alloc_space / inuse_space)        4.20x", report)
        self.assertIn("freed        (alloc_objects - inuse_objects)    32", report)
        self.assertIn("precision    (every allocation tracked)         exact", report)

    def test_attribution_only_capture_withholds_every_ratio(self) -> None:
        """JFR's live view samples call sites from a bounded queue: it shows
        where memory came from, never how much. Ratios over it would be made up."""
        table = spine.folded_to_table({"inuse_space": write_folded(self.tmp / "live.folded", {"main;cache": 4096})})
        report = spine.bucket_report(table, spine.read_meta(write_meta(self.tmp, precision="attribution_only")))
        self.assertIn("turnover     (alloc_space / inuse_space)        —", report)
        self.assertIn("live / RSS   (inuse_space / VmRSS)              —", report)
        self.assertIn("not a heap census", report)
        # The attribution itself is still shown — it is the useful part.
        self.assertIn("main;cache".rpartition(";")[2], report)

    def test_resolve_tools_names_the_missing_binary(self) -> None:
        """A stale PROFILE_* path otherwise surfaces as `None failed with exit
        code 127` from deep inside a subprocess call."""
        saved = os.environ.pop("PROFILE_PB2FOLDED")
        try:
            with self.assertRaises(spine.ProfileError) as caught:
                spine.resolve_tools()
            self.assertIn("pb2folded", str(caught.exception))
        finally:
            os.environ["PROFILE_PB2FOLDED"] = saved


if __name__ == "__main__":
    unittest.main()
