use rust_workloads::{
    fragmentation, matmul, pointer_chase, quicksort, retained_growth, string_churn,
};

const SEED: u64 = 42;

#[test]
fn matmul_loop_orders_agree() {
    let n = 16;
    let a = matmul::random_matrix(n, SEED);
    let b = matmul::random_matrix(n, SEED + 1);
    // Per-element accumulation order is identical in both variants, so the
    // float results match exactly.
    assert_eq!(
        matmul::multiply_ijk(&a, &b, n),
        matmul::multiply_ikj(&a, &b, n)
    );
}

#[test]
fn quicksort_sorts() {
    let mut v = quicksort::random_vec(1000, SEED);
    let mut expected = v.clone();
    expected.sort_unstable();
    quicksort::quicksort(&mut v);
    assert_eq!(v, expected);
}

#[test]
fn pointer_chase_visits_every_slot_once() {
    let n = 97;
    let perm = pointer_chase::build_cycle(n, SEED);
    let expected = n * (n - 1) / 2;
    assert_eq!(pointer_chase::chase_sum(&perm), expected);
    assert_eq!(pointer_chase::array_sum(&perm), expected);
}

#[test]
fn retained_growth_retains_requested_bytes() {
    let retained = retained_growth::grow(8, 1024);
    assert_eq!(retained_growth::retained_bytes(&retained), 8 * 1024);
}

#[test]
fn string_churn_builds_full_string() {
    assert_eq!(string_churn::concat(10, "ab").len(), 20);
}

#[test]
fn fragmentation_keeps_every_other_block_doubled() {
    let (survivors, stats) = fragmentation::fragment(100, SEED);
    assert_eq!(stats.survivors, 50);
    assert_eq!(survivors.len(), 50);
    assert_eq!(
        stats.live_bytes,
        survivors.iter().map(Vec::len).sum::<usize>()
    );
    assert!(
        survivors
            .iter()
            .all(|b| b.len() % 2 == 0 && b.len() >= 1024)
    );
}
