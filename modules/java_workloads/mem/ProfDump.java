package monorepo.workloads;

import java.io.IOException;
import java.nio.file.Path;

import jdk.jfr.Recording;

/**
 * Shared shim for the one-shot memory workloads: a JFR recording of
 * weighted allocation samples (jdk.ObjectAllocationSample), dumped after
 * the workload ran. Both calls are no-ops unless MEMPROF_OUT is set;
 * start must run before the workload allocates. The recording is stopped
 * before the dump so the dump's own allocations stay out of the profile.
 */
final class ProfDump {
    private static Recording recording;

    private ProfDump() {
    }

    static void start() {
        if (System.getenv("MEMPROF_OUT") == null) {
            return;
        }
        recording = new Recording();
        recording.enable("jdk.ObjectAllocationSample").with("throttle", "1000/s");
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
        recording.stop();
        recording.dump(Path.of(out));
        recording.close();
        return out;
    }
}
