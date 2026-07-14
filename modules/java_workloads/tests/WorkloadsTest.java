package monorepo.workloads;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.Arrays;

import org.junit.jupiter.api.Test;

class WorkloadsTest {
    private static final long SEED = 42;

    @Test
    void matmulLoopOrdersAgree() {
        int n = 16;
        double[] a = Matmul.randomMatrix(n, SEED);
        double[] b = Matmul.randomMatrix(n, SEED + 1);
        // Per-element accumulation order is identical in both variants, so
        // the float results match exactly.
        assertArrayEquals(Matmul.multiplyIjk(a, b, n), Matmul.multiplyIkj(a, b, n));
    }

    @Test
    void quicksortSorts() {
        long[] v = Quicksort.randomSlice(1000, SEED);
        long[] expected = Arrays.copyOf(v, v.length);
        Arrays.sort(expected);
        Quicksort.quicksort(v);
        assertArrayEquals(expected, v);
    }

    @Test
    void pointerChaseVisitsEverySlotOnce() {
        int n = 97;
        int[] perm = PointerChase.buildCycle(n, SEED);
        long expected = (long) n * (n - 1) / 2;
        assertEquals(expected, PointerChase.chaseSum(perm));
        assertEquals(expected, PointerChase.arraySum(perm));
    }

    @Test
    void retainedGrowthRetainsRequestedBytes() {
        byte[][] retained = RetainedGrowth.grow(8, 1024);
        assertEquals(8 * 1024, RetainedGrowth.retainedBytes(retained));
    }

    @Test
    void stringChurnBuildsFullString() {
        assertEquals(20, StringChurn.concat(10, "ab").length());
    }
}
