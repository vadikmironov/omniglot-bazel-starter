//! Steadily grows a retained, reachable-but-never-reread heap: the live-heap
//! signature a profiler attributes to this allocation site.

/// Allocate `chunks` chunks of `chunk_bytes` each and retain them all. The
/// caller must hold the result alive while the heap profile is dumped.
pub fn grow(chunks: usize, chunk_bytes: usize) -> Vec<Vec<u8>> {
    let mut retained = Vec::with_capacity(chunks);
    for i in 0..chunks {
        retained.push(vec![(i % 251) as u8; chunk_bytes]);
    }
    retained
}

pub fn retained_bytes(retained: &[Vec<u8>]) -> usize {
    retained.iter().map(Vec::len).sum()
}
