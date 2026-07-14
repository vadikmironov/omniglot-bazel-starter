// Quicksort bench: recursive call tree renders as a quicksort →
// partition flamegraph tower, with a branch-miss story on random input.

package monorepo.workloads;

import java.util.Arrays;
import java.util.concurrent.TimeUnit;

import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Fork;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;

@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@State(Scope.Benchmark)
@Fork(1)
public class BenchQuicksort {
    private static final int DEFAULT_N = 1_000_000;

    private long[] input;

    @Setup
    public void setup() {
        input = Quicksort.randomSlice(WorkloadN.workloadN(DEFAULT_N), 42);
    }

    @Benchmark
    public long[] quicksort() {
        long[] buf = Arrays.copyOf(input, input.length);
        Quicksort.quicksort(buf);
        return buf;
    }
}
