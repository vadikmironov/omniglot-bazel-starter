//! One-shot string-churn workload: massive transient allocation traffic with
//! a tiny live heap at dump time.

mod prof_dump;

use rust_workloads::{string_churn, workload_n};

const DEFAULT_PIECES: usize = 8_000;

fn main() {
    let pieces = workload_n(DEFAULT_PIECES);
    let s = string_churn::concat(pieces, "0123456789abcdef");
    let out = prof_dump::dump();
    println!("built {} bytes; heap profile: {}", s.len(), out.display());
}
