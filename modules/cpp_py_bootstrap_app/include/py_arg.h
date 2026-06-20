#pragma once

#include <string>
#include <variant>

/// Argument type for call_in_subinterpreter().
///
/// Supports the common Python scalar types. C++20 P0608R3 prevents narrowing
/// conversions, so {1} selects int (not bool) and {"hello"} selects std::string
/// (not bool). Use {true}/{false} for bool arguments explicitly.
using PyArg = std::variant<bool, int, long long, double, std::string>;
