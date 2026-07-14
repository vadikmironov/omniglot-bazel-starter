// Shared bench entrypoint: wraps benchmark::RunSpecifiedBenchmarks in
// gperftools ProfilerStart/Stop when CPUPROF_OUT is set (the //tools/profile
// runner sets it), so the profile covers the benchmark run only and lands at
// a deterministic path. Without CPUPROF_OUT the benches run unprofiled.
// gperftools' own CPUPROFILE env activation is avoided: it resolves the
// output path twice and the second pass appends the pid.

#include <benchmark/benchmark.h>
#include <gperftools/profiler.h>

#include <cstdio>
#include <cstdlib>

auto main(int argc, char** argv) -> int {
    benchmark::Initialize(&argc, argv);
    if (benchmark::ReportUnrecognizedArguments(argc, argv)) {
        return 1;
    }
    const char* profile_out = std::getenv("CPUPROF_OUT");
    if (profile_out != nullptr && ProfilerStart(profile_out) == 0) {
        std::fprintf(stderr, "warning: ProfilerStart(%s) failed; benches run unprofiled\n", profile_out);
        profile_out = nullptr;
    }
    benchmark::RunSpecifiedBenchmarks();
    if (profile_out != nullptr) {
        ProfilerStop();
    }
    benchmark::Shutdown();
    return 0;
}
