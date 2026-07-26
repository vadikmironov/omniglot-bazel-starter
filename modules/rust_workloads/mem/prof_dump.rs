//! Shared shim for the one-shot memory workloads: tcmalloc's heap profiler
//! dumped in gperftools' legacy format while the workload's heap is live (the
//! //tools/profile runner converts it to pprof), plus the footprint sidecar it
//! folds into the report.
//!
//! Linking tcmalloc is all it takes — it interposes malloc/free, so Rust's
//! allocations are captured without a `#[global_allocator]`. It records every
//! allocation rather than sampling, and reports live *and* cumulative bytes
//! *and* object counts, so Rust fills all four buckets exactly, like C++.
//! jemalloc cannot: it removed `opt.prof_accum` in 5.0.0 because cumulative
//! counts oblige it to retain every unique backtrace for the whole run.

use std::ffi::{CString, c_char};
use std::path::{Path, PathBuf};

unsafe extern "C" {
    fn HeapProfilerStart(prefix: *const c_char);
    fn HeapProfilerDump(reason: *const c_char);
    fn HeapProfilerStop();
}

/// Begin recording. Must run before the workload allocates — tcmalloc only
/// tracks allocations made after this point. A no-op without `MEMPROF_OUT`.
pub fn start() {
    if let Some(prefix) = out_prefix() {
        let prefix = CString::new(prefix.into_os_string().into_encoded_bytes())
            .expect("MEMPROF_OUT contains an interior NUL");
        unsafe { HeapProfilerStart(prefix.as_ptr()) };
    }
}

/// Dump to `<MEMPROF_OUT>.NNNN.heap` and return the prefix. Call it while the
/// workload's heap is still live.
pub fn dump() -> PathBuf {
    let Some(prefix) = out_prefix() else {
        return PathBuf::new();
    };
    let reason = CString::new("workload done").expect("reason");
    unsafe {
        HeapProfilerDump(reason.as_ptr());
        HeapProfilerStop();
    }
    write_meta(&prefix);
    prefix
}

fn out_prefix() -> Option<PathBuf> {
    std::env::var_os("MEMPROF_OUT").map(PathBuf::from)
}

/// Live bytes over VmRSS is the only signal separating fragmentation from
/// genuine retention; tcmalloc records every allocation, so the figures are
/// exact and the runner never discounts them.
fn write_meta(prefix: &Path) {
    let (current, peak) = read_rss();
    let meta = format!("vmrss_bytes={current}\nvmhwm_bytes={peak}\nprecision=exact\n");
    // Best-effort: a missing sidecar only costs the footprint ratios.
    let _ = std::fs::write(prefix.with_extension("meta"), meta);
}

/// Current and peak resident set size in bytes, or zeroes where /proc is
/// unavailable (macOS).
fn read_rss() -> (u64, u64) {
    let Ok(status) = std::fs::read_to_string("/proc/self/status") else {
        return (0, 0);
    };
    let mut rss = (0, 0);
    for line in status.lines() {
        let Some((field, value)) = line.split_once(':') else {
            continue;
        };
        let kib = || -> u64 {
            value
                .trim()
                .trim_end_matches(" kB")
                .parse::<u64>()
                .unwrap_or(0)
                * 1024
        };
        match field {
            "VmRSS" => rss.0 = kib(),
            "VmHWM" => rss.1 = kib(),
            _ => {}
        }
    }
    rss
}
