//! One-shot fragmentation workload: live bytes drop while jemalloc's mapped
//! memory stays high.

mod prof_dump;

use rust_workloads::{fragmentation, workload_n};

const DEFAULT_BLOCKS: usize = 50_000;

fn main() {
    let blocks = workload_n(DEFAULT_BLOCKS);
    let (survivors, stats) = fragmentation::fragment(blocks, 42);
    let out = prof_dump::dump();
    println!(
        "{} surviving blocks, {} live bytes; heap profile: {}",
        survivors.len(),
        stats.live_bytes,
        out.display()
    );
}
