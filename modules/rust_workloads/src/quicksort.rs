//! In-place recursive quicksort over seeded random input; the recursion gives
//! the flamegraph its `quicksort → partition` tower.

use rand::rngs::StdRng;
use rand::{RngExt, SeedableRng};

pub fn random_vec(n: usize, seed: u64) -> Vec<u64> {
    let mut rng = StdRng::seed_from_u64(seed);
    (0..n).map(|_| rng.random()).collect()
}

pub fn quicksort(v: &mut [u64]) {
    if v.len() <= 1 {
        return;
    }
    let mid = partition(v);
    let (lo, hi) = v.split_at_mut(mid);
    quicksort(lo);
    quicksort(&mut hi[1..]);
}

/// Lomuto partition around the last element; returns the pivot's final slot.
fn partition(v: &mut [u64]) -> usize {
    let pivot = v[v.len() - 1];
    let mut store = 0;
    for i in 0..v.len() - 1 {
        if v[i] <= pivot {
            v.swap(store, i);
            store += 1;
        }
    }
    v.swap(store, v.len() - 1);
    store
}
