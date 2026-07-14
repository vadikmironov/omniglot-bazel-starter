// One-shot string-churn workload: massive transient allocation traffic
// with a tiny live heap at dump time.

package monorepo.workloads;

public final class MemStringChurn {
    private static final int DEFAULT_PIECES = 8000;

    private MemStringChurn() {
    }

    public static void main(String[] args) throws Exception {
        int pieces = WorkloadN.workloadN(DEFAULT_PIECES);
        ProfDump.start();
        String built = StringChurn.concat(pieces, "0123456789abcdef");
        String out = ProfDump.dump();
        System.out.printf("built %d chars; heap recording: %s%n", built.length(), out);
    }
}
