// NOLINTBEGIN(misc-include-cleaner) — Python.h is CPython's umbrella header; sub-headers are internal
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <atomic>
#include <cstdint>
#include <memory>

#include "cpp_library.h"

namespace {

struct ModuleState {
    std::atomic<uint64_t> invocation_count;
};

auto get_module_state(PyObject* self) -> ModuleState* {
    return static_cast<ModuleState*>(PyModule_GetState(self));
}

extern "C" {
// NOLINTNEXTLINE(bugprone-easily-swappable-parameters) — CPython callback signature
static auto get_hello_world_string_py_wrapper(PyObject* self, PyObject* args) -> PyObject* {
    unsigned int level = cpp_library::HelloWorldStringPrinter::DEFAULT_LEVEL;

    // please see https://docs.python.org/3/c-api/arg.html#parsing-arguments
    if (PyArg_ParseTuple(args, "|I", &level) == 0) {  // NOLINT(cppcoreguidelines-pro-type-vararg,hicpp-vararg)
        return nullptr;
    }

    const auto result = cpp_library::HelloWorldStringPrinter::get_hello_world_string(level);

    if (auto* state = get_module_state(self); state != nullptr) {
        state->invocation_count.fetch_add(1, std::memory_order_relaxed);
    }

    return PyUnicode_FromStringAndSize(result.data(), static_cast<Py_ssize_t>(result.length()));
}

static auto get_invocation_count(PyObject* self, PyObject* /*args*/) -> PyObject* {
    auto* state = get_module_state(self);
    if (state == nullptr) {
        PyErr_SetString(PyExc_RuntimeError, "Module state not initialized");
        return nullptr;
    }
    const uint64_t count = state->invocation_count.load(std::memory_order_relaxed);
    return PyLong_FromUnsignedLongLong(count);
}

static auto cpp_py_ext_module_exec(PyObject* self) -> int {
    // Initialize module state
    auto* state = get_module_state(self);
    if (state == nullptr) {
        PyErr_SetString(PyExc_RuntimeError, "Module state not initialized during Py_mod_exec slot");
        return -1;
    }
    new (&state->invocation_count) std::atomic<uint64_t>(0);
    return 0;
}

static void cpp_py_ext_module_free(void* self) {
    auto* state = get_module_state(static_cast<PyObject*>(self));
    if (state != nullptr) {
        std::destroy_at(&state->invocation_count);
    }
}
}

// NOLINTNEXTLINE(cppcoreguidelines-avoid-non-const-global-variables,cppcoreguidelines-avoid-c-arrays,hicpp-avoid-c-arrays,modernize-avoid-c-arrays)
PyMethodDef cpp_py_ext_module_methods[] = {
    {"get_hello_world_string_py_wrapper", get_hello_world_string_py_wrapper, METH_VARARGS,
     "Function wrapper over cpp_library static get_hello_world_string function."},
    {"get_invocation_count", get_invocation_count, METH_NOARGS,
     "Returns the number of successful get_hello_world_string invocations."},
    {nullptr, nullptr, 0, nullptr} /* Sentinel */
};

// NOLINTNEXTLINE(cppcoreguidelines-avoid-non-const-global-variables,cppcoreguidelines-avoid-c-arrays,hicpp-avoid-c-arrays,modernize-avoid-c-arrays)
PyModuleDef_Slot cpp_py_ext_module_slots[] = {
    {Py_mod_exec, reinterpret_cast<void*>(cpp_py_ext_module_exec)},  // NOLINT(cppcoreguidelines-pro-type-reinterpret-cast)
#ifdef Py_GIL_DISABLED
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},
#endif
    {0, nullptr} /* Sentinel */
};

// NOLINTNEXTLINE(cppcoreguidelines-avoid-non-const-global-variables)
struct PyModuleDef cpp_py_ext_module = {
    .m_base = PyModuleDef_HEAD_INIT,  // NOLINT(hicpp-signed-bitwise)
    .m_name = "cpp_py_ext_module_impl",
    .m_doc =
        "Test module showcasing Bazel's rules_python support for PyModule "
        "extensions.",
    .m_size = sizeof(ModuleState),
    .m_methods = cpp_py_ext_module_methods,  // NOLINT(cppcoreguidelines-pro-bounds-array-to-pointer-decay,hicpp-no-array-decay)
    .m_slots = cpp_py_ext_module_slots,      // NOLINT(cppcoreguidelines-pro-bounds-array-to-pointer-decay,hicpp-no-array-decay)
    .m_traverse = nullptr,
    .m_clear = nullptr,
    .m_free = cpp_py_ext_module_free,
};

}  // namespace

extern "C" {
PyMODINIT_FUNC PyInit_cpp_py_ext_module_impl(void) {  // NOLINT(modernize-use-trailing-return-type)
    return PyModuleDef_Init(&cpp_py_ext_module);
}
}
// NOLINTEND(misc-include-cleaner)
