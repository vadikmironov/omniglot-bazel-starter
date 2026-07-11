//! One-shot retained-growth workload: the heap profile attributes the whole
//! live heap to the growth site.

mod prof_dump;

use rust_workloads::{retained_growth, workload_n};

const DEFAULT_CHUNKS: usize = 65_536;
const CHUNK_BYTES: usize = 1024;

fn main() {
    let chunks = workload_n(DEFAULT_CHUNKS);
    let retained = retained_growth::grow(chunks, CHUNK_BYTES);
    let out = prof_dump::dump();
    println!(
        "retained {} bytes in {} chunks; heap profile: {}",
        retained_growth::retained_bytes(&retained),
        retained.len(),
        out.display()
    );
}
