//! Pointer chasing over a single-cycle permutation versus a contiguous sum of
//! the same buffer: dependent random loads against streaming loads.

use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};

/// Single-cycle permutation of 0..n (Sattolo's algorithm): following
/// `i = perm[i]` from any start visits every slot exactly once.
pub fn build_cycle(n: usize, seed: u64) -> Vec<usize> {
    let mut rng = StdRng::seed_from_u64(seed);
    let mut perm: Vec<usize> = (0..n).collect();
    for i in (1..n).rev() {
        let j = rng.random_range(0..i);
        perm.swap(i, j);
    }
    perm
}

/// Walk the cycle once from slot 0, summing the visited indices.
pub fn chase_sum(perm: &[usize]) -> usize {
    let mut idx = 0;
    let mut acc = 0;
    for _ in 0..perm.len() {
        acc += idx;
        idx = perm[idx];
    }
    acc
}

/// Contiguous sum of the same buffer — the streaming counterpart.
pub fn array_sum(perm: &[usize]) -> usize {
    perm.iter().sum()
}
