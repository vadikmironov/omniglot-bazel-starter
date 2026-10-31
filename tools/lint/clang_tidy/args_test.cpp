#include "tools/lint/clang_tidy/args.h"

#include <gtest/gtest.h>

#include <string>
#include <vector>

namespace clang_tidy {
namespace {

using Args = std::vector<std::string>;

constexpr auto gcc = "external/gcc_toolchain_x86_64_15_2_0";
constexpr auto clang_headers = "external/llvm_toolchain_llvm/lib/clang/23/include";

// NOLINTBEGIN(cppcoreguidelines-avoid-non-const-global-variables,cppcoreguidelines-owning-memory,cert-err58-cpp,modernize-use-trailing-return-type)
TEST(SplitConfigTest, OneArgPerLine) {
    EXPECT_EQ(split_config("-nostdinc\n-isystem\nexternal/foo\n"), (Args{"-nostdinc", "-isystem", "external/foo"}));
}

TEST(SplitConfigTest, QuotedArgs) {
    EXPECT_EQ(split_config("'-DGREETING=\"hello world\"'\n'-DAPOSTROPHE='\\''x'\\'''\n''\n"),
              (Args{"-DGREETING=\"hello world\"", "-DAPOSTROPHE='x'", ""}));
}

TEST(SplitConfigTest, NoTrailingNewline) {
    EXPECT_EQ(split_config("-c\nfoo.cpp"), (Args{"-c", "foo.cpp"}));
}

TEST(WithClangHeadersTest, SwapsGccHeadersInOneArg) {
    const std::string headers = std::string(gcc) + "/lib/gcc/x86_64-linux/15.2.0/include";
    EXPECT_EQ(with_clang_headers({"-nostdinc", "-isystem" + headers, "-isystem" + headers + "/"}, clang_headers),
              (Args{"-nostdinc", std::string("-isystem") + clang_headers, std::string("-isystem") + clang_headers}));
}

TEST(WithClangHeadersTest, SwapsGccHeadersInTheNextArg) {
    EXPECT_EQ(with_clang_headers({"-isystem", std::string(gcc) + "/lib/gcc/aarch64-linux/15.2.0/include"}, clang_headers),
              (Args{"-isystem", clang_headers}));
}

TEST(WithClangHeadersTest, KeepsGccsOtherHeaders) {
    const Args args{
        "-isystem" + std::string(gcc) + "/include/c++/15.2.0",
        "-isystem" + std::string(gcc) + "/lib/gcc/x86_64-linux/15.2.0/include-fixed",
        "-isystem" + std::string(gcc) + "/sysroot/usr/include",
        "-I",
        std::string(gcc) + "/lib/gcc/x86_64-linux/15.2.0/include",
    };
    EXPECT_EQ(with_clang_headers(args, clang_headers), args);
}

TEST(WithClangHeadersTest, KeepsLlvmToolchainArgs) {
    const Args args{"-isystem", clang_headers, "-isystemexternal/llvm_toolchain_llvm/include/c++/v1"};
    EXPECT_EQ(with_clang_headers(args, clang_headers), args);
}
// NOLINTEND(cppcoreguidelines-avoid-non-const-global-variables,cppcoreguidelines-owning-memory,cert-err58-cpp,modernize-use-trailing-return-type)

}  // namespace
}  // namespace clang_tidy
