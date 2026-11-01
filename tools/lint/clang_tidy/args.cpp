#include "tools/lint/clang_tidy/args.h"

#include <cctype>
#include <cstddef>
#include <regex>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace clang_tidy {
namespace {

constexpr std::string_view isystem = "-isystem";

auto is_gcc_headers(std::string_view path) -> bool {
    static const std::regex gcc_headers(R"((^|/)lib/gcc/[^/]+/[^/]+/include/?$)");
    return std::regex_search(path.begin(), path.end(), gcc_headers);
}

}  // namespace

auto split_config(std::string_view text) -> std::vector<std::string> {
    std::vector<std::string> args;
    std::string arg;
    bool in_arg = false;
    bool quoted = false;
    for (std::size_t i = 0; i < text.size(); ++i) {
        const char c = text[i];
        if (quoted) {
            if (c == '\'') {
                quoted = false;
            } else {
                arg += c;
            }
        } else if (c == '\'') {
            quoted = true;
            in_arg = true;
        } else if (c == '\\' && i + 1 < text.size()) {
            arg += text[++i];
            in_arg = true;
        } else if (std::isspace(static_cast<unsigned char>(c)) != 0) {
            if (in_arg) {
                args.push_back(std::exchange(arg, {}));
                in_arg = false;
            }
        } else {
            arg += c;
            in_arg = true;
        }
    }
    if (in_arg) {
        args.push_back(std::move(arg));
    }
    return args;
}

auto with_clang_headers(const std::vector<std::string>& args,
                        std::string_view clang_headers)
    -> std::vector<std::string> {
    std::vector<std::string> result;
    result.reserve(args.size());
    for (const std::string& arg : args) {
        if (arg.starts_with(isystem) && is_gcc_headers(std::string_view(arg).substr(isystem.size()))) {
            result.push_back(std::string(isystem).append(clang_headers));
        } else if (!result.empty() && result.back() == isystem && is_gcc_headers(arg)) {
            result.emplace_back(clang_headers);
        } else {
            result.push_back(arg);
        }
    }
    return result;
}

}  // namespace clang_tidy
