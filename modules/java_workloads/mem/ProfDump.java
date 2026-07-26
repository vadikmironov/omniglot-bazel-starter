package monorepo.workloads;

import java.io.IOException;
import java.lang.management.ManagementFactory;
import java.nio.file.Files;
import java.nio.file.Path;

import jdk.jfr.Recording;

/**
 * Shared shim for the one-shot memory workloads: a JFR recording of weighted
 * allocation samples (jdk.ObjectAllocationSample), dumped after the workload
 * ran, plus the footprint sidecar the //tools/profile runner folds into its
 * report. Both calls are no-ops unless MEMPROF_OUT is set; start must run
 * before the workload allocates. The recording is stopped before the dump so
 * the dump's own allocations stay out of the profile.
 *
 * <p>JFR attributes allocated <em>bytes</em> and nothing else — it reports no
 * object count and no per-site live heap. See the README in this directory for
 * why, and for what the runner therefore leaves blank.
 */
// DoNotCallGarbageCollectionExplicitly: forcing a collection is the point here
// — the live heap must be read after garbage is gone, or the figure includes
// what the workload already dropped.
// LawOfDemeter: reaching the heap figure means going through the MXBean and its
// usage snapshot; the JDK offers no flatter accessor, and hoisting the
// intermediates into locals does not satisfy the rule either.
@SuppressWarnings({"PMD.DoNotCallGarbageCollectionExplicitly", "PMD.LawOfDemeter"})
final class ProfDump {
    // JFR's own profile.jfc setting. Throttling is per-second, so the sample
    // count reflects the throttle rather than the workload — which is exactly
    // why an object count cannot be recovered from it.
    private static final String ALLOC_THROTTLE = "300/s";

    private static Recording recording;

    private ProfDump() {
    }

    static void start() {
        if (System.getenv("MEMPROF_OUT") == null) {
            return;
        }
        recording = new Recording();
        recording.enable("jdk.ObjectAllocationSample").with("throttle", ALLOC_THROTTLE);
        recording.start();
    }

    /**
     * Dumps the recording to $MEMPROF_OUT and returns the path.
     */
    static String dump() throws IOException {
        String out = System.getenv("MEMPROF_OUT");
        if (out == null) {
            return "";
        }
        // Collect first so the reported live heap excludes garbage, then read it
        // before stopping the recording so both describe the same instant.
        System.gc();
        final var memory = ManagementFactory.getMemoryMXBean();
        final var heap = memory.getHeapMemoryUsage();
        final long heapLive = heap.getUsed();
        recording.stop();
        recording.dump(Path.of(out));
        recording.close();
        writeMeta(out, heapLive);
        return out;
    }

    /**
     * Records footprint and precision alongside the recording. heapLive is the
     * whole heap — exact, but including JVM and JFR overhead and not attributed
     * to call sites, so the runner reports it separately from the flamegraph's
     * allocation columns rather than mixing the two scopes.
     */
    private static void writeMeta(String out, long heapLive) {
        final long[] rss = readRss();
        final String meta = "vmrss_bytes=" + rss[0] + "\n"
                          + "vmhwm_bytes=" + rss[1] + "\n"
                          + "heap_live_bytes=" + heapLive + "\n"
                          + "precision=sampled_events:" + ALLOC_THROTTLE.replace("/s", "") + "\n";
        try {
            Files.writeString(Path.of(out + ".meta"), meta);
        } catch (IOException e) {
            // Best-effort: a missing sidecar only costs the footprint ratios,
            // so report it and let the profile itself still be written.
            System.err.println("could not write " + out + ".meta: " + e.getMessage());
        }
    }

    /**
     * Current and peak RSS in bytes, or zeroes where /proc is unavailable.
     */
    private static long[] readRss() {
        final long[] rss = {0L, 0L};
        try {
            for (String line : Files.readAllLines(Path.of("/proc/self/status"))) {
                final int index = line.startsWith("VmRSS:") ? 0 : line.startsWith("VmHWM:") ? 1
                                                                                            : -1;
                if (index >= 0) {
                    rss[index] = Long.parseLong(line.replaceAll("\\D+", "")) * 1024;
                }
            }
        } catch (IOException | NumberFormatException e) {
            return new long[] {0L, 0L};
        }
        return rss;
    }
}
