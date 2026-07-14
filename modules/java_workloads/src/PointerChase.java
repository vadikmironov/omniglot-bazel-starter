package monorepo.workloads;

import java.util.SplittableRandom;

/**
 * Pointer chasing over a single-cycle permutation versus a contiguous
 * sum of the same buffer: dependent random loads against streaming loads.
 */
@SuppressWarnings("PMD.ShortVariable")
public final class PointerChase {
    private PointerChase() {
    }

    /**
     * Single-cycle permutation of 0..n (Sattolo's algorithm): following
     * i = perm[i] from any start visits every slot exactly once.
     */
    public static int[] buildCycle(int n, long seed) {
        SplittableRandom rng = new SplittableRandom(seed);
        int[] perm = new int[n];
        for (int i = 0; i < n; i++) {
            perm[i] = i;
        }
        for (int i = n - 1; i >= 1; i--) {
            int j = rng.nextInt(i);
            int tmp = perm[i];
            perm[i] = perm[j];
            perm[j] = tmp;
        }
        return perm;
    }

    /**
     * Walks the cycle once from slot 0, summing the visited indices.
     */
    public static long chaseSum(int[] perm) {
        int idx = 0;
        long acc = 0;
        for (int unused : perm) {
            acc += idx;
            idx = perm[idx];
        }
        return acc;
    }

    /**
     * The streaming counterpart: a contiguous sum of the buffer.
     */
    public static long arraySum(int[] perm) {
        long acc = 0;
        for (int v : perm) {
            acc += v;
        }
        return acc;
    }
}
