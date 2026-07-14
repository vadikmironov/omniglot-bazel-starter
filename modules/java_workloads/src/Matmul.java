package monorepo.workloads;

import java.util.SplittableRandom;

/**
 * Dense n×n matrix multiply in two loop orders: ijk strides column-wise
 * through b (cache-hostile), ikj streams both operands row-major.
 */
@SuppressWarnings("PMD.ShortVariable")
public final class Matmul {
    private Matmul() {
    }

    /**
     * Row-major n×n matrix filled from a seeded PRNG.
     */
    public static double[] randomMatrix(int n, long seed) {
        SplittableRandom rng = new SplittableRandom(seed);
        double[] m = new double[n * n];
        for (int i = 0; i < m.length; i++) {
            m[i] = rng.nextDouble();
        }
        return m;
    }

    public static double[] multiplyIjk(double[] a, double[] b, int n) {
        double[] c = new double[n * n];
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                double acc = 0.0;
                for (int k = 0; k < n; k++) {
                    acc += a[i * n + k] * b[k * n + j];
                }
                c[i * n + j] = acc;
            }
        }
        return c;
    }

    public static double[] multiplyIkj(double[] a, double[] b, int n) {
        double[] c = new double[n * n];
        for (int i = 0; i < n; i++) {
            for (int k = 0; k < n; k++) {
                double aik = a[i * n + k];
                for (int j = 0; j < n; j++) {
                    c[i * n + j] += aik * b[k * n + j];
                }
            }
        }
        return c;
    }
}
