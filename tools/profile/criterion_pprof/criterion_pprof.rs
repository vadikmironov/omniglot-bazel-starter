//! CPU capture for criterion benches: a criterion `Profiler` that samples with
//! pprof-rs for the length of a `--profile-time` run and writes `profile.pb`
//! into criterion's per-benchmark directory, where the //tools/profile runner
//! picks it up.
//!
//! pprof-rs ships the same integration behind its own `criterion` feature, but
//! that feature depends on criterion 0.5, which would pin every bench in the
//! repo to it. The trait is two methods over pprof's core API, so the benches
//! link this instead and criterion stays free to move.
//!
//! A bench opts in through criterion's config:
//!
//! ```ignore
//! use criterion_pprof::PProfProfiler;
//!
//! criterion_group! {
//!     name = benches;
//!     config = Criterion::default().with_profiler(PProfProfiler::new(100));
//!     targets = bench_thing
//! }
//! ```

use std::fs::{self, File};
use std::io::Write;
use std::os::raw::c_int;
use std::path::Path;

use criterion::profiler::Profiler;
use pprof::ProfilerGuard;
use pprof::protos::Message;

/// Samples the profiled benchmark at `frequency` Hz.
pub struct PProfProfiler {
    frequency: c_int,
    guard: Option<ProfilerGuard<'static>>,
}

impl PProfProfiler {
    #[must_use]
    pub fn new(frequency: c_int) -> Self {
        Self {
            frequency,
            guard: None,
        }
    }
}

impl Profiler for PProfProfiler {
    fn start_profiling(&mut self, _benchmark_id: &str, _benchmark_dir: &Path) {
        self.guard = Some(ProfilerGuard::new(self.frequency).expect("start the pprof sampler"));
    }

    fn stop_profiling(&mut self, _benchmark_id: &str, benchmark_dir: &Path) {
        let Some(guard) = self.guard.take() else {
            return;
        };
        let profile = guard
            .report()
            .build()
            .expect("build the pprof report")
            .pprof()
            .expect("convert the report to pprof");
        let bytes = profile.write_to_bytes().expect("encode the pprof profile");

        fs::create_dir_all(benchmark_dir).expect("create the criterion benchmark directory");
        let path = benchmark_dir.join("profile.pb");
        File::create(&path)
            .and_then(|mut f| f.write_all(&bytes))
            .unwrap_or_else(|e| panic!("write {}: {e}", path.display()));
    }
}
