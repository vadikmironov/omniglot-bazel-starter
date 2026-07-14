// Matrix-multiply bench: the ijk vs ikj loop-order gap is cache
// behaviour — in-process profiles show a hot loop, an external
// sampler's cache counters explain the difference.

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
public class BenchMatmul {
    private static final int DEFAULT_N = 256;

    private int n;
    private double[] a;
    private double[] b;

    @Setup
    public void setup() {
        n = WorkloadN.workloadN(DEFAULT_N);
        a = Matmul.randomMatrix(n, 42);
        b = Matmul.randomMatrix(n, 43);
    }

    @Benchmark
    public double[] ijk() {
        return Matmul.multiplyIjk(a, b, n);
    }

    @Benchmark
    public double[] ikj() {
        return Matmul.multiplyIkj(a, b, n);
    }
}
