#pragma once

// Include this instead of <Python.h>.
//
// MSVC's pyconfig.h picks the import library with a #pragma comment(lib, ...)
// guarded on _DEBUG, asking for python3XX_d.lib when it is set. Bazel's -c dbg
// selects the debug CRT (/MDd), which defines _DEBUG — but a standard CPython
// distribution ships only python3XX.lib, so the link fails with
//
//   LINK : fatal error LNK1104: cannot open file 'python314_d.lib'
//
// unless you installed the debug binaries. Undefining _DEBUG across the include
// leaves the CRT selection alone and only steers that pragma to the release
// library, which is the same approach pybind11 and nanobind take.
//
// Everything outside the include still sees _DEBUG, so assert() and the
// debug-CRT behaviour are unaffected.

#ifdef _DEBUG
#undef _DEBUG
#include <Python.h>
#define _DEBUG
#else
#include <Python.h>
#endif
