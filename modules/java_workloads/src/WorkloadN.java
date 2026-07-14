package monorepo.workloads;

/**
 * Workload sizing shared by the bench and memory targets.
 */
public final class WorkloadN {
    private WorkloadN() {
    }

    /**
     * Workload size from WORKLOAD_N, falling back to the target's default.
     */
    public static int workloadN(int fallback) {
        String raw = System.getenv("WORKLOAD_N");
        if (raw == null) {
            return fallback;
        }
        try {
            return Integer.parseInt(raw);
        } catch (NumberFormatException e) {
            return fallback;
        }
    }
}
