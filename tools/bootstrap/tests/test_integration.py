"""Integration tests — Bazel-in-Bazel end-to-end verification.

Scaffolds real repositories, injects hello-world modules, and runs
``bazel build`` and ``bazel test`` inside them. The negative lint check
scaffolds a separate lint-enabled repo, injects deliberately bad code,
regenerates the ``lint_test`` rules with ``bazel run //:lint_gen``, and
verifies that the ``lint``-tagged tests fail. It runs only for
single-language subsets (each linter once, on a small scaffold) — the
multi-language + lint graph is too large to repin within the bootstrap's
600s lock-refresh timeout.

Tagged ``manual`` so they are excluded from ``bazel test //...``.
Each subset spins up cold nested Bazel servers, so the suite is slow;
run it single-shard with a generous timeout and live progress::

    bazel test //tools/bootstrap/tests:test_integration \\
        --test_timeout=5400 --test_output=streamed

NOT sharded on purpose: shard_count is static and each shard would duplicate
the multi-GB toolchain cache, blowing a small CI runner's disk. Drive a single
subset directly when iterating::

    python -m unittest test_integration.TestIntegration.test_java_only
"""

import os
import shutil
import subprocess
import tempfile
import textwrap
import time
import unittest
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from bootstrap.manifest import BootstrapManifest, effective_languages, load_manifest, resolve_files
from bootstrap.scaffolder import refresh_lock_files, scaffold_repo

REPO_NAME = "test_repo"

# ── Live progress logging ────────────────────────────────────────────
_START = time.monotonic()


def _log(msg: str) -> None:
    """Print a flushed, elapsed-timestamped progress marker for streamed output."""
    print(f"[+{time.monotonic() - _START:6.1f}s] {msg}", flush=True)


# ── Source root ──────────────────────────────────────────────────────


def _find_source_root() -> Path:
    return Path(__file__).resolve().parents[3]


# ── Bazel command runner ─────────────────────────────────────────────

# Every subset scaffolds into its own temp workspace, so each nested Bazel run
# has a cold output_base. They share one cache tree (downloads via
# --repository_cache, compiled action outputs via --disk_cache) so the toolchain
# set is fetched/built once and reused across subsets; without it every subset
# recompiles everything — which made the suite crawl and tripped the build
# timeout on the all-languages subset.
#
# Set $INTEGRATION_TEST_CACHE_DIR to reuse the tree across runs (e.g. an
# actions/cache path in CI); otherwise a fresh temp dir per run. In CI the
# within-run reuse alone is the big win and needs no setup. If you *do* persist
# it, bound it: --disk_cache has no built-in garbage collection, so pair it with
# an eviction policy (or --experimental_disk_cache_gc_max_size) to stay under
# the runner's cache-size limit.
_SHARED_CACHE: Path | None = None


def _cache_dir() -> Path:
    global _SHARED_CACHE  # noqa: PLW0603
    if _SHARED_CACHE is None:
        env = os.environ.get("INTEGRATION_TEST_CACHE_DIR")
        _SHARED_CACHE = Path(env) if env else Path(tempfile.mkdtemp(prefix="bootstrap_integ_cache_"))
        _SHARED_CACHE.mkdir(parents=True, exist_ok=True)
    return _SHARED_CACHE


def _bazel(cwd: Path, command: str, *args: str, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    """Run a Bazel command in a workspace, reusing the shared cache tree.

    Cache flags are omitted for ``shutdown``/``clean`` (they reject build flags;
    ``clean --expunge`` is how each workspace's output_base is reclaimed).
    """
    cmd = ["bazel", command]
    if command not in ("shutdown", "clean"):
        cache = _cache_dir()
        cmd += [f"--repository_cache={cache / 'repo'}", f"--disk_cache={cache / 'disk'}"]
    cmd += list(args)
    return subprocess.run(  # noqa: S603
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


# ── Hello-world module generators ───────────────────────────────────


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content))


def _create_python_hello(modules: Path) -> None:
    d = modules / "hello_py"
    _write(
        d / "BUILD",
        """\
        load("@rules_python//python:defs.bzl", "py_binary", "py_library", "py_test")

        py_library(name = "lib", srcs = ["hello.py"], imports = ["."])
        py_binary(name = "hello_py", srcs = ["main.py"], main = "main.py", deps = [":lib"])
        py_test(name = "hello_test", srcs = ["hello_test.py"], deps = [":lib"])
    """,
    )
    _write(
        d / "hello.py",
        """\
        def greet() -> str:
            return "Hello, World!"
    """,
    )
    _write(
        d / "main.py",
        """\
        from hello import greet

        print(greet())
    """,
    )
    _write(
        d / "hello_test.py",
        """\
        import unittest

        from hello import greet


        class GreetTest(unittest.TestCase):
            def test_greet(self) -> None:
                self.assertEqual(greet(), "Hello, World!")


        if __name__ == "__main__":
            unittest.main()
    """,
    )


def _create_cpp_hello(modules: Path) -> None:
    d = modules / "hello_cpp"
    _write(
        d / "BUILD",
        """\
        load("@rules_cc//cc:defs.bzl", "cc_binary", "cc_library", "cc_test")

        cc_library(name = "lib", srcs = ["hello.cpp"], hdrs = ["hello.h"])
        cc_binary(name = "hello_cpp", srcs = ["main.cpp"], deps = [":lib"])
        cc_test(
            name = "hello_test",
            srcs = ["hello_test.cpp"],
            deps = [":lib", "@googletest//:gtest", "@googletest//:gtest_main"],
        )
    """,
    )
    _write(
        d / "hello.h",
        """\
        #pragma once
        #include <string_view>

        inline constexpr std::string_view greet() {
            return "Hello, World!";
        }
    """,
    )
    _write(
        d / "hello.cpp",
        """\
        #include "hello.h"
    """,
    )
    _write(
        d / "main.cpp",
        """\
        #include <iostream>

        #include "hello.h"

        auto main() -> int {
            std::cout << greet() << '\\n';
            return 0;
        }
    """,
    )
    _write(
        d / "hello_test.cpp",
        """\
        #include <gtest/gtest.h>

        #include "hello.h"

        TEST(HelloTest, Greet) {
            EXPECT_EQ(greet(), "Hello, World!");
        }
    """,
    )


def _create_rust_hello(modules: Path) -> None:
    d = modules / "hello_rust"
    _write(
        d / "BUILD",
        """\
        load("@rules_rust//rust:defs.bzl", "rust_binary", "rust_library", "rust_test")

        rust_library(name = "lib", srcs = ["src/lib.rs"])
        rust_binary(name = "hello_rust", srcs = ["src/main.rs"], deps = [":lib"])
        rust_test(name = "hello_test", srcs = ["tests/hello_test.rs"], deps = [":lib"])
    """,
    )
    _write(
        d / "src" / "lib.rs",
        """\
        pub fn greet() -> &'static str {
            "Hello, World!"
        }
    """,
    )
    _write(
        d / "src" / "main.rs",
        """\
        extern crate lib;

        fn main() {
            println!("{}", lib::greet());
        }
    """,
    )
    _write(
        d / "tests" / "hello_test.rs",
        """\
        extern crate lib;

        #[test]
        fn test_greet() {
            assert_eq!(lib::greet(), "Hello, World!");
        }
    """,
    )


def _create_java_hello(modules: Path) -> None:
    d = modules / "hello_java"
    _write(
        d / "BUILD",
        """\
        load("@rules_java//java:defs.bzl", "java_binary", "java_library")
        load("//tools/java/testing:java_test_suite.bzl", "java_test_suite")

        java_library(name = "lib", srcs = ["src/main/java/hello/HelloLib.java"])

        java_binary(
            name = "hello_java",
            srcs = ["src/main/java/hello/Main.java"],
            main_class = "hello.Main",
            deps = [":lib"],
        )

        java_test_suite(
            name = "hello_test",
            srcs = ["src/test/java/hello/HelloLibTest.java"],
            deps = [":lib"],
        )
    """,
    )
    _write(
        d / "src" / "main" / "java" / "hello" / "HelloLib.java",
        """\
        package hello;

        public final class HelloLib {

            private HelloLib() {}

            public static String greet() {
                return "Hello, World!";
            }
        }
    """,
    )
    _write(
        d / "src" / "main" / "java" / "hello" / "Main.java",
        """\
        package hello;

        public final class Main {

            private Main() {}

            public static void main(String[] args) {
                System.out.println(HelloLib.greet());
            }
        }
    """,
    )
    _write(
        d / "src" / "test" / "java" / "hello" / "HelloLibTest.java",
        """\
        package hello;

        import static org.junit.jupiter.api.Assertions.assertEquals;

        import org.junit.jupiter.api.Test;

        public class HelloLibTest {

            @Test
            public void testGreet() {
                assertEquals("Hello, World!", HelloLib.greet());
            }
        }
    """,
    )


def _create_go_hello(modules: Path) -> None:
    d = modules / "hello_go"
    _write(
        d / "BUILD",
        """\
        load("@rules_go//go:def.bzl", "go_binary", "go_library", "go_test")

        go_library(name = "lib", srcs = ["hello.go"])
        go_binary(name = "hello_go", srcs = ["main.go"])
        go_test(name = "hello_test", srcs = ["hello_test.go"], embed = [":lib"])
    """,
    )
    _write(
        d / "hello.go",
        """\
        package hello_go

        // Greet returns a greeting string.
        func Greet() string {
        \treturn "Hello, World!"
        }
    """,
    )
    _write(
        d / "main.go",
        """\
        package main

        import "fmt"

        func main() {
        \tfmt.Println("Hello, World!")
        }
    """,
    )
    _write(
        d / "hello_test.go",
        """\
        package hello_go

        import "testing"

        func TestGreet(t *testing.T) {
        \tif got := Greet(); got != "Hello, World!" {
        \t\tt.Errorf("got %q, want %q", got, "Hello, World!")
        \t}
        }
    """,
    )


# Dispatch table: language → hello-world creator
_HELLO_CREATORS: dict[str, Callable[[Path], None]] = {
    "python": _create_python_hello,
    "cpp": _create_cpp_hello,
    "rust": _create_rust_hello,
    "java": _create_java_hello,
    "go": _create_go_hello,
}


# ── Bad-code module generators (for negative lint tests) ─────────────


def _create_python_bad(modules: Path) -> None:
    d = modules / "bad_py"
    _write(
        d / "BUILD",
        """\
        load("@rules_python//python:defs.bzl", "py_library")

        py_library(name = "bad_py", srcs = ["bad.py"])
    """,
    )
    _write(
        d / "bad.py",
        """\
        import os

        x = 1
    """,
    )


def _create_cpp_bad(modules: Path) -> None:
    d = modules / "bad_cpp"
    _write(
        d / "BUILD",
        """\
        load("@rules_cc//cc:defs.bzl", "cc_library")

        cc_library(name = "bad_cpp", srcs = ["bad.cpp"])
    """,
    )
    # Use of C-style cast triggers clang-tidy cppcoreguidelines-pro-type-cstyle-cast
    _write(
        d / "bad.cpp",
        """\
        auto bad_cast() -> int {
            double x = 3.14;
            return (int)x;
        }
    """,
    )


def _create_rust_bad(modules: Path) -> None:
    d = modules / "bad_rust"
    _write(
        d / "BUILD",
        """\
        load("@rules_rust//rust:defs.bzl", "rust_library")

        rust_library(name = "bad_rust", srcs = ["bad.rs"])
    """,
    )
    # Using .len() == 0 instead of .is_empty() triggers clippy::len_zero
    _write(
        d / "bad.rs",
        """\
        pub fn check_empty(v: &Vec<i32>) -> bool {
            v.len() == 0
        }
    """,
    )


def _create_java_bad(modules: Path) -> None:
    d = modules / "bad_java"
    _write(
        d / "BUILD",
        """\
        load("@rules_java//java:defs.bzl", "java_library")

        java_library(name = "bad_java", srcs = ["src/main/java/bad/Bad.java"])
    """,
    )
    # Empty catch block triggers PMD EmptyCatchBlock
    _write(
        d / "src" / "main" / "java" / "bad" / "Bad.java",
        """\
        package bad;

        public class Bad {
            public static void doSomething() {
                try {
                    System.out.println("test");
                } catch (Exception e) {
                }
            }
        }
    """,
    )


_BAD_CREATORS: dict[str, Callable[[Path], None]] = {
    "python": _create_python_bad,
    "cpp": _create_cpp_bad,
    "rust": _create_rust_bad,
    "java": _create_java_bad,
    # Go has no rules_lint linter (nogo runs at build time) — skip
}


# ── Test class ───────────────────────────────────────────────────────


class TestIntegration(unittest.TestCase):
    """End-to-end integration tests with real Bazel invocations."""

    source_root: Path
    manifest: BootstrapManifest

    @classmethod
    def setUpClass(cls) -> None:
        cls.source_root = _find_source_root()
        cls.manifest = load_manifest(cls.source_root / "tools" / "bootstrap" / "bootstrap_manifest.toml")
        # The Java Maven repin runs an *unpinned* coursier fetch, for which
        # rules_jvm_external derives the coursier cache dir from $HOME and
        # relativizes downloaded artifact paths against it (coursier.bzl). Under
        # `bazel test` the nested Bazel's $HOME is unset/divergent, so that path
        # parse fails ("Error while trying to parse the path of file in the
        # coursier cache"). Pinning COURSIER_CACHE to a stable shared dir makes
        # Bazel and the coursier subprocess agree (pinned builds are unaffected —
        # they set COURSIER_CACHE to a repo-local dir themselves). Shared across
        # subsets so the Maven universe is downloaded once.
        os.environ["COURSIER_CACHE"] = str(_cache_dir() / "coursier")

    @contextmanager
    def _workspace(self, selected_languages: set[str], selected_features: set[str]) -> Iterator[Path]:
        """Scaffold a repo, yield it, then reclaim it — the shared setup/teardown
        for every subset (positive build/test and lint-negative alike).

        Languages required by the selected features (e.g. ``go`` for ``lint``)
        are promoted, mirroring the CLI, so composite-file section filtering and
        file resolution see the same effective language set.

        On exit the workspace's output_base is expunged (extracted toolchains run
        to GBs) and its temp dir removed. Expunging here — not via a deferred
        tearDown — keeps peak disk at ~one workspace, which matters on
        space-limited CI runners. The shared repository/disk caches survive
        (separate dirs), preserving cross-subset reuse.
        """
        languages = effective_languages(self.manifest, selected_languages, selected_features)
        label = "_".join(sorted(languages | selected_features))
        workspace = Path(tempfile.mkdtemp(prefix=f"integ_{label}_"))
        try:
            resolved = resolve_files(self.manifest, languages, selected_features)
            scaffold_repo(
                source_root=self.source_root,
                target_path=workspace,
                repo_name=REPO_NAME,
                module_dir="modules",
                selected_languages=languages,
                selected_features=selected_features,
                manifest=self.manifest,
                resolved=resolved,
            )

            # Mirror the real bootstrap (cli.py), which repins the Java Maven lock
            # after scaffolding: the shipped maven_install.json is the source's
            # full pin, but scaffolds strip palantir/jsoup (exclude) and
            # pmd/spotbugs (lint off), so without a repin rules_jvm_external's
            # input-artifacts hash never matches and `bazel build` fails. Only
            # Java is repinned — rules_python/cargo/go don't hard-fail on a
            # lock/manifest mismatch, so their (cold, uncached, minutes-long)
            # refreshes are pure dead weight here.
            if "java" in languages:
                results = refresh_lock_files(target_path=workspace, repo_name=REPO_NAME, selected_languages={"java"})
                self.assertTrue(results.get("java"), "Java Maven lock repin failed")

            yield workspace
        finally:
            _bazel(workspace, "clean", "--expunge", timeout=300)
            shutil.rmtree(workspace, ignore_errors=True)

    def _assert_bazel_build(self, workspace: Path) -> None:
        """bazel build //modules/... must succeed."""
        result = _bazel(workspace, "build", "//modules/...")
        self.assertEqual(
            result.returncode,
            0,
            f"bazel build failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
        )

    def _assert_bazel_test(self, workspace: Path) -> None:
        """bazel test //modules/... must succeed."""
        result = _bazel(workspace, "test", "//modules/...")
        self.assertEqual(
            result.returncode,
            0,
            f"bazel test failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
        )

    def _assert_lint_negative(self, selected: set[str]) -> None:
        """Verify the scaffolded lint feature catches deliberately bad code.

        Scaffolds a lint-enabled repo, injects bad modules, regenerates the
        per-target ``lint_test`` rules with ``bazel run //:lint_gen``, then runs
        the ``lint``-tagged tests (excluded from the default set) and requires
        at least one to fail.
        """
        lintable = selected & _BAD_CREATORS.keys()
        if not lintable:
            return  # no lintable languages in this subset

        with self._workspace(selected, {"lint"}) as workspace:
            modules = workspace / "modules"
            for lang in lintable:
                _BAD_CREATORS[lang](modules)

            gen = _bazel(workspace, "run", "//:lint_gen")
            self.assertEqual(
                gen.returncode,
                0,
                f"lint_gen failed:\nSTDOUT:\n{gen.stdout}\nSTDERR:\n{gen.stderr}",
            )

            # --fail_on_violation makes lint_test compare against an empty report
            # (assert_output_empty) instead of just the linter exit code, so
            # clang-tidy/clippy findings — which exit 0 — are caught too. We only
            # lint bad modules here, so the rules_lint#899 false-positive on clean
            # clang-tidy targets is irrelevant.
            result = _bazel(
                workspace,
                "test",
                "--@aspect_rules_lint//lint:fail_on_violation",
                "--test_tag_filters=lint",
                "//modules/...",
            )
            # Exit 3 is Bazel's "build OK, but a test failed" — exactly the lint
            # gate firing on bad code. A bare `!= 0` would also pass on exit 1
            # (analysis/build error, e.g. a lint rule referencing a sibling the
            # scaffold forgot to ship), masking a broken scaffold as a caught
            # lint. Pin to 3 so only a genuine test failure counts.
            self.assertEqual(
                result.returncode,
                3,
                f"expected lint tests to fail on bad code (exit 3), got exit {result.returncode}:\n"
                f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
            )

    def _run_full_check(self, selected: set[str]) -> None:
        """Run all integration checks for a language subset."""
        name = ",".join(sorted(selected))

        # 1. Scaffold with clean modules; build and test must pass.
        _log(f"[{name}] scaffold …")
        t0 = time.monotonic()
        with self._workspace(selected, set()) as workspace:
            modules = workspace / "modules"
            for lang in selected:
                if lang in _HELLO_CREATORS:
                    _HELLO_CREATORS[lang](modules)
            _log(f"[{name}] scaffold OK ({time.monotonic() - t0:.1f}s)")

            _log(f"[{name}] build …")
            t0 = time.monotonic()
            self._assert_bazel_build(workspace)
            _log(f"[{name}] build OK ({time.monotonic() - t0:.1f}s)")

            _log(f"[{name}] test …")
            t0 = time.monotonic()
            self._assert_bazel_test(workspace)
            _log(f"[{name}] test OK ({time.monotonic() - t0:.1f}s)")

        # 2. A lint-enabled scaffold must catch bad code — but only run this for
        # single-language subsets. Each linter is exercised once on a small
        # scaffold, while the multi-language + lint scaffold is avoided: its
        # ~14k-target graph makes the Java Maven repin's cold analysis blow past
        # the bootstrap's hardcoded 600s lock-refresh timeout. Multi-language
        # *positive* build/test above still runs for every subset.
        if len(selected) == 1:
            _log(f"[{name}] lint-negative …")
            t0 = time.monotonic()
            self._assert_lint_negative(selected)
            _log(f"[{name}] lint-negative OK ({time.monotonic() - t0:.1f}s)")

    # ── Representative subset tests ──────────────────────────────────

    def test_python_only(self) -> None:
        """Single language: Python."""
        self._run_full_check({"python"})

    def test_cpp_only(self) -> None:
        """Single language: C++ (LLVM toolchain)."""
        self._run_full_check({"cpp"})

    def test_rust_only(self) -> None:
        """Single language: Rust (independent toolchain)."""
        self._run_full_check({"rust"})

    def test_java_only(self) -> None:
        """Single language: Java (LLVM shared dep without C++)."""
        self._run_full_check({"java"})

    def test_go_only(self) -> None:
        """Single language: Go (nogo, go.mod)."""
        self._run_full_check({"go"})

    # Multi-language subsets cover cross-language integration via the positive
    # build/test only (lint-negative is single-language, see _run_full_check).
    # Two representatives are kept; the redundant python_java / python_rust_go
    # combinations are dropped to keep wall time in budget.
    def test_cpp_java(self) -> None:
        """Shared LLVM dependency — both consumers present."""
        self._run_full_check({"cpp", "java"})

    def test_all_languages(self) -> None:
        """Full set — closest to the source repo."""
        self._run_full_check({"python", "cpp", "rust", "java", "go"})


if __name__ == "__main__":
    unittest.main()
