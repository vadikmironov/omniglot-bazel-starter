//! O(n²) string concatenation: every round allocates a fresh string and
//! copies the whole accumulator — high transient allocation rate, tiny live
//! heap at any instant.

pub fn concat(pieces: usize, piece: &str) -> String {
    let mut acc = String::new();
    for _ in 0..pieces {
        acc = format!("{acc}{piece}");
    }
    acc
}
