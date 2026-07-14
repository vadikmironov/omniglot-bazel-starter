package monorepo.workloads;

import java.util.Arrays;

/**
 * Steadily grows a retained, reachable-but-never-reread heap: the
 * live-heap signature a profiler attributes to this allocation site.
 */
public final class RetainedGrowth {
    private RetainedGrowth() {
    }

    /**
     * Allocates chunks chunks of chunkBytes each and retains them all.
     */
    public static byte[][] grow(int chunks, int chunkBytes) {
        byte[][] retained = new byte[chunks][];
        for (int i = 0; i < chunks; i++) {
            byte[] chunk = new byte[chunkBytes];
            Arrays.fill(chunk, (byte) (i % 251));
            retained[i] = chunk;
        }
        return retained;
    }

    public static long retainedBytes(byte[][] retained) {
        long total = 0;
        for (byte[] chunk : retained) {
            total += chunk.length;
        }
        return total;
    }
}
