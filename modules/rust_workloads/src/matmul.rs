//! Dense n×n matrix multiply in two loop orders: `ijk` strides column-wise
//! through `b` (cache-hostile), `ikj` streams both operands row-major.

use rand::rngs::StdRng;
use rand::{RngExt, SeedableRng};

/// Row-major n×n matrix filled from a seeded PRNG.
pub fn random_matrix(n: usize, seed: u64) -> Vec<f64> {
    let mut rng = StdRng::seed_from_u64(seed);
    (0..n * n).map(|_| rng.random()).collect()
}

pub fn multiply_ijk(a: &[f64], b: &[f64], n: usize) -> Vec<f64> {
    let mut c = vec![0.0; n * n];
    for i in 0..n {
        for j in 0..n {
            let mut acc = 0.0;
            for k in 0..n {
                acc += a[i * n + k] * b[k * n + j];
            }
            c[i * n + j] = acc;
        }
    }
    c
}

pub fn multiply_ikj(a: &[f64], b: &[f64], n: usize) -> Vec<f64> {
    let mut c = vec![0.0; n * n];
    for i in 0..n {
        for k in 0..n {
            let aik = a[i * n + k];
            for j in 0..n {
                c[i * n + j] += aik * b[k * n + j];
            }
        }
    }
    c
}
