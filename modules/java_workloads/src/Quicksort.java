package monorepo.workloads;

import java.util.SplittableRandom;

/**
 * In-place recursive quicksort over seeded random input; the recursion
 * gives the flamegraph its quicksort → partition tower.
 */
@SuppressWarnings("PMD.ShortVariable")
public final class Quicksort {
    private Quicksort() {
    }

    public static long[] randomSlice(int n, long seed) {
        SplittableRandom rng = new SplittableRandom(seed);
        long[] v = new long[n];
        for (int i = 0; i < n; i++) {
            v[i] = rng.nextLong();
        }
        return v;
    }

    public static void quicksort(long[] v) {
        quicksort(v, 0, v.length);
    }

    private static void quicksort(long[] v, int lo, int hi) {
        if (hi - lo <= 1) {
            return;
        }
        int mid = partition(v, lo, hi);
        quicksort(v, lo, mid);
        quicksort(v, mid + 1, hi);
    }

    /**
     * Lomuto partition around the last element; returns the pivot's final slot.
     */
    private static int partition(long[] v, int lo, int hi) {
        long pivot = v[hi - 1];
        int store = lo;
        for (int i = lo; i < hi - 1; i++) {
            if (v[i] <= pivot) {
                long tmp = v[store];
                v[store] = v[i];
                v[i] = tmp;
                store++;
            }
        }
        long tmp = v[store];
        v[store] = v[hi - 1];
        v[hi - 1] = tmp;
        return store;
    }
}
