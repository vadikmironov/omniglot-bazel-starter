// Pointer-chase bench: serially dependent random loads (memory-latency
// bound) against a contiguous sum of the same buffer (bandwidth bound).

package monorepo.workloads;

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
public class BenchPointerChase {
    private static final int DEFAULT_N = 1 << 22;

    private int[] perm;

    @Setup
    public void setup() {
        perm = PointerChase.buildCycle(WorkloadN.workloadN(DEFAULT_N), 42);
    }

    @Benchmark
    public long chase() {
        return PointerChase.chaseSum(perm);
    }

    @Benchmark
    public long arraySum() {
        return PointerChase.arraySum(perm);
    }
}
