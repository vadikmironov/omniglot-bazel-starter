// Runs clang-tidy with clang's built-in headers in place of GCC's.
//
// rules_lint gives clang-tidy the compile command of the C++ toolchain in use.
// Under --config=gcc_hermetic, that command has -nostdinc and lists GCC's own
// header directory, lib/gcc/<target>/<version>/include. Its intrinsics headers
// call GCC builtins that clang doesn't have, so any code that includes
// <immintrin.h> fails to parse. This swaps that directory for clang's built-in
// headers, as clang does itself when it compiles against a GCC installation.
// Keeping GCC's directory as well doesn't work: clang's limits.h expects the
// system's limits.h next, and GCC's would come between them. Under the LLVM
// toolchain no -isystem matches, so the include order stays as it is.
//
// rules_lint's clang_tidy_wrapper.bash calls it as clang-tidy:
//
//     clang_tidy <clang-tidy args> -- <compiler args>
//
// where the compiler args may hold --config FILE, a clang config file with the
// toolchain's args in it.

#include <unistd.h>

#include <algorithm>
#include <cerrno>
#include <exception>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <memory>
#include <span>
#include <sstream>
#include <stdexcept>
#include <string>
#include <system_error>
#include <vector>

#include "rules_cc/cc/runfiles/runfiles.h"
#include "tools/lint/clang_tidy/args.h"

namespace {

using rules_cc::cc::runfiles::Runfiles;

constexpr auto clang_tidy_runfile = "llvm_toolchain_llvm/bin/clang-tidy";

auto read_file(const std::filesystem::path& path) -> std::string {
    const std::ifstream file(path);
    if (!file) {
        throw std::runtime_error("can't read " + path.string());
    }
    std::ostringstream text;
    text << file.rdbuf();
    return text.str();
}

// Where clang-tidy finds its built-in headers: lib/clang/<version>/include,
// next to its bin directory.
auto clang_headers(const std::filesystem::path& clang_tidy) -> std::filesystem::path {
    const std::filesystem::path lib_clang = clang_tidy.parent_path().parent_path() / "lib" / "clang";
    std::vector<std::filesystem::path> versions;
    for (const auto& entry : std::filesystem::directory_iterator(lib_clang)) {
        versions.push_back(entry.path());
    }
    if (versions.size() != 1) {
        throw std::runtime_error("expected one version in " + lib_clang.string());
    }
    return versions.front() / "include";
}

// The compiler args, with each --config FILE replaced by the args in the file.
auto expand_configs(std::span<const std::string> args) -> std::vector<std::string> {
    std::vector<std::string> expanded;
    for (auto arg = args.begin(); arg != args.end(); ++arg) {
        if (*arg == "--config" && std::next(arg) != args.end()) {
            std::ranges::move(clang_tidy::split_config(read_file(*++arg)), std::back_inserter(expanded));
        } else {
            expanded.push_back(*arg);
        }
    }
    return expanded;
}

auto run(std::span<char*> argv) -> int {
    std::string error;
    const std::unique_ptr<Runfiles> runfiles(Runfiles::Create(argv.front(), BAZEL_CURRENT_REPOSITORY, &error));
    if (runfiles == nullptr) {
        throw std::runtime_error(error);
    }
    std::string clang_tidy = runfiles->Rlocation(clang_tidy_runfile);
    if (clang_tidy.empty()) {
        throw std::runtime_error(std::string(clang_tidy_runfile) + " isn't in the runfiles");
    }

    std::vector<std::string> args(argv.begin() + 1, argv.end());
    const auto split = std::ranges::find(args, "--");
    if (split != args.end()) {
        const std::vector<std::string> compiler_args = clang_tidy::with_clang_headers(
            expand_configs(std::span(std::next(split), args.end())), clang_headers(clang_tidy).string());
        args.erase(std::next(split), args.end());
        args.insert(args.end(), compiler_args.begin(), compiler_args.end());
    }

    std::vector<char*> exec_args{clang_tidy.data()};
    for (std::string& arg : args) {
        exec_args.push_back(arg.data());
    }
    exec_args.push_back(nullptr);
    execv(clang_tidy.c_str(), exec_args.data());
    throw std::runtime_error("can't run " + clang_tidy + ": " + std::generic_category().message(errno));
}

}  // namespace

auto main(int argc, char* argv[]) -> int {
    try {
        return run(std::span(argv, argc));
    } catch (const std::exception& e) {
        std::cerr << "clang_tidy: " << e.what() << '\n';
        return 1;
    }
}
