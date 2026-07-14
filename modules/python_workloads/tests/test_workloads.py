import unittest

from python_workloads.matmul import multiply_ijk, multiply_ikj, random_matrix
from python_workloads.pointer_chase import array_sum, build_cycle, chase_sum
from python_workloads.quicksort import quicksort, random_slice
from python_workloads.retained_growth import grow, retained_bytes
from python_workloads.string_churn import concat

SEED = 42


class WorkloadsTest(unittest.TestCase):
    def test_matmul_loop_orders_agree(self):
        n = 16
        a = random_matrix(n, SEED)
        b = random_matrix(n, SEED + 1)
        # Per-element accumulation order is identical in both variants, so
        # the float results match exactly.
        self.assertEqual(multiply_ijk(a, b, n), multiply_ikj(a, b, n))

    def test_quicksort_sorts(self):
        v = random_slice(1000, SEED)
        expected = sorted(v)
        quicksort(v)
        self.assertEqual(expected, v)

    def test_pointer_chase_visits_every_slot_once(self):
        n = 97
        perm = build_cycle(n, SEED)
        expected = n * (n - 1) // 2
        self.assertEqual(expected, chase_sum(perm))
        self.assertEqual(expected, array_sum(perm))

    def test_retained_growth_retains_requested_bytes(self):
        retained = grow(8, 1024)
        self.assertEqual(8 * 1024, retained_bytes(retained))

    def test_string_churn_builds_full_string(self):
        self.assertEqual(20, len(concat(10, "ab")))


if __name__ == "__main__":
    unittest.main()
