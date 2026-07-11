//! Fragmentation: allocate many variably sized blocks, free every other one,
//! then grow each survivor — live bytes shrink while the allocator's mapped
//! memory stays high.

use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};

pub struct FragStats {
    pub survivors: usize,
    pub live_bytes: usize,
}

/// Returns the surviving blocks (hold them alive while the heap profile is
/// dumped) and their stats.
pub fn fragment(blocks: usize, seed: u64) -> (Vec<Vec<u8>>, FragStats) {
    let mut rng = StdRng::seed_from_u64(seed);
    let all: Vec<Vec<u8>> = (0..blocks)
        .map(|_| vec![0xA5_u8; rng.random_range(512..8192)])
        .collect();

    let mut survivors: Vec<Vec<u8>> = all
        .into_iter()
        .enumerate()
        .filter_map(|(i, block)| (i % 2 == 0).then_some(block))
        .collect();
    for block in &mut survivors {
        let target = block.len() * 2;
        block.resize(target, 0x5A);
    }

    let stats = FragStats {
        survivors: survivors.len(),
        live_bytes: survivors.iter().map(Vec::len).sum(),
    };
    (survivors, stats)
}
