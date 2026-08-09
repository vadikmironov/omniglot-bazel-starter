//! Pins the contract the //tools/profile runner relies on: after criterion
//! hands the profiler a benchmark directory, that directory holds a
//! `profile.pb` the pprof pipeline can parse.
//!
//! Driving the trait directly rather than through a criterion run keeps this a
//! test of the shim: criterion's own `--profile-time` plumbing is exercised by
//! the bench targets.

use std::fs;
use std::path::PathBuf;
use std::time::{Duration, Instant};

use criterion::profiler::Profiler;
use criterion_pprof::PProfProfiler;
use pprof::protos::{Message, Profile};

/// Bazel's per-test scratch directory, with a plain temp-dir fallback.
fn scratch(name: &str) -> PathBuf {
    let base = std::env::var_os("TEST_TMPDIR").map_or_else(std::env::temp_dir, PathBuf::from);
    base.join(name)
}

/// Burns CPU time so the sampler's SIGPROF timer has something to record.
fn burn(duration: Duration) {
    let deadline = Instant::now() + duration;
    let mut acc = 0u64;
    while Instant::now() < deadline {
        for i in 0..10_000u64 {
            acc = acc.wrapping_add(i * i);
        }
    }
    assert!(acc > 0, "the busy loop must not be optimized away");
}

#[test]
fn writes_a_parsable_profile_into_the_benchmark_dir() {
    // A path criterion has not created yet: the profiler owns creating it.
    let dir = scratch("parsable/thing/profile");
    let mut profiler = PProfProfiler::new(999);

    profiler.start_profiling("thing", &dir);
    burn(Duration::from_millis(300));
    profiler.stop_profiling("thing", &dir);

    let bytes = fs::read(dir.join("profile.pb")).expect("profile.pb in the benchmark dir");
    let profile = Profile::parse_from_bytes(&bytes).expect("parse as a pprof profile");
    assert!(
        !profile.sample_type.is_empty(),
        "profile declares no sample type"
    );
    assert!(
        !profile.sample.is_empty(),
        "no samples recorded over 300ms of CPU time"
    );
}

#[test]
fn stop_without_start_writes_nothing() {
    let dir = scratch("no_start");
    PProfProfiler::new(999).stop_profiling("thing", &dir);
    assert!(
        !dir.join("profile.pb").exists(),
        "wrote a profile without sampling"
    );
}
