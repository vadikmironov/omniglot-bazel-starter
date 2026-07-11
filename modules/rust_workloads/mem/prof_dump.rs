//! Shared shim for the one-shot memory workloads: jemalloc as the global
//! allocator with heap profiling baked on, dumped as a pprof profile.

use core::ffi::c_char;
use std::path::PathBuf;

use tikv_jemallocator::Jemalloc;

#[global_allocator]
static ALLOC: Jemalloc = Jemalloc;

/// Heap profiling on by default; the `MALLOC_CONF` environment variable
/// still overrides this at startup. Sampling every 2^15 bytes (32 KiB)
/// registers even small live heaps like the churn workload's final string.
#[allow(non_upper_case_globals)]
#[unsafe(export_name = "malloc_conf")]
pub static malloc_conf: &c_char =
    unsafe { &*c"prof:true,prof_active:true,lg_prof_sample:15".as_ptr() };

/// Dump a pprof heap profile to `$MEMPROF_OUT` (default `memprof.pb`) and
/// return the path. Call it while the workload's heap is still live.
pub fn dump() -> PathBuf {
    let out = std::env::var_os("MEMPROF_OUT")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("memprof.pb"));
    let mut ctl = jemalloc_pprof::PROF_CTL
        .as_ref()
        .expect("jemalloc heap profiling inactive; run with MALLOC_CONF=prof:true,prof_active:true")
        .blocking_lock();
    let profile = ctl.dump_pprof().expect("failed to dump pprof heap profile");
    std::fs::write(&out, profile).expect("failed to write heap profile");
    out
}
