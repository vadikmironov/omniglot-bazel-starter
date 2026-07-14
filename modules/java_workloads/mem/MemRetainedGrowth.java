// One-shot retained-growth workload: the allocation profile attributes
// the whole live heap to the growth site.

package monorepo.workloads;

import java.lang.ref.Reference;

public final class MemRetainedGrowth {
    private static final int DEFAULT_CHUNKS = 65_536;
    private static final int CHUNK_BYTES = 1024;

    private MemRetainedGrowth() {
    }

    public static void main(String[] args) throws Exception {
        int chunks = WorkloadN.workloadN(DEFAULT_CHUNKS);
        ProfDump.start();
        byte[][] retained = RetainedGrowth.grow(chunks, CHUNK_BYTES);
        String out = ProfDump.dump();
        System.out.printf("retained %d bytes in %d chunks; heap recording: %s%n",
            RetainedGrowth.retainedBytes(retained), retained.length, out);
        Reference.reachabilityFence(retained);
    }
}
