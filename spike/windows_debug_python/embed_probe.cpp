// Q1 probe for #183: does a real debug CPython make Windows `-c dbg` work?
//
// Deliberately includes <Python.h> with no guard around it. Compiled /MDd,
// _DEBUG is defined, so pyconfig.h emits
// #pragma comment(lib, "python314_d.lib") and the link either resolves it from
// the debug build or fails. That link is the primary result of this probe.
//
// The runtime checks mirror what modules/cpp_py_bootstrap_app actually does:
// PEP 741 init, a GIL release/restore round trip, and an own-GIL
// sub-interpreter.

#include <Python.h>

#include <cstdio>

namespace {

auto report_init_error(PyInitConfig* config, const char* what) -> int {
    const char* err_msg = nullptr;
    (void)PyInitConfig_GetError(config, &err_msg);
    std::printf("FAIL: %s: %s\n", what, err_msg != nullptr ? err_msg : "(unknown error)");
    return 1;
}

auto run(const char* snippet) -> bool { return PyRun_SimpleString(snippet) == 0; }

}  // namespace

auto main(int argc, char** argv) -> int {
    if (argc < 2) {
        std::printf("usage: embed_probe <python-home>\n");
        return 2;
    }

#ifdef _DEBUG
    std::printf("compiled with _DEBUG defined (debug CRT)\n");
#else
    std::printf("compiled WITHOUT _DEBUG - not the configuration under test\n");
#endif

    PyInitConfig* config = PyInitConfig_Create();
    if (config == nullptr) {
        std::printf("FAIL: PyInitConfig_Create\n");
        return 1;
    }

    if (PyInitConfig_SetStr(config, "home", argv[1]) < 0) {
        const int rc = report_init_error(config, "PyInitConfig_SetStr(home)");
        PyInitConfig_Free(config);
        return rc;
    }

    if (Py_InitializeFromInitConfig(config) < 0) {
        const int rc = report_init_error(config, "Py_InitializeFromInitConfig");
        PyInitConfig_Free(config);
        return rc;
    }
    PyInitConfig_Free(config);

    std::printf("initialized: %s\n", Py_GetVersion());

    // The interpreter is only a debug build if these are present.
    if (not run("import sys, sysconfig\n"
                "assert sysconfig.get_config_var('Py_DEBUG') == 1, 'not a debug interpreter'\n"
                "assert hasattr(sys, 'gettotalrefcount'), 'no gettotalrefcount'\n"
                "print('  Py_DEBUG      :', sysconfig.get_config_var('Py_DEBUG'))\n"
                "print('  ABIFLAGS      :', sysconfig.get_config_var('ABIFLAGS'))\n"
                "print('  EXT_SUFFIX    :', sysconfig.get_config_var('EXT_SUFFIX'))\n")) {
        std::printf("FAIL: debug-interpreter probe raised\n");
        return 1;
    }

    // What the debug build actually buys: sys.gettotalrefcount does not exist
    // on a release interpreter, so leaks like this one are invisible there.
    if (not run("import sys\n"
                "base = sys.gettotalrefcount()\n"
                "held = [object() for _ in range(1000)]\n"
                "leaked = sys.gettotalrefcount() - base\n"
                "del held\n"
                "recovered = leaked - (sys.gettotalrefcount() - base)\n"
                "print('  refs held by 1000 objects :', leaked)\n"
                "print('  refs returned on release  :', recovered)\n"
                "assert leaked >= 1000, 'refcount did not track allocations'\n"
                "assert recovered >= 1000, 'refcount did not track frees'\n")) {
        std::printf("FAIL: refcount tracking probe raised\n");
        return 1;
    }

    // GIL release / restore, as gil_release_guard.h does.
    PyThreadState* saved = PyEval_SaveThread();
    PyEval_RestoreThread(saved);
    std::printf("  GIL save/restore: ok\n");

    // Own-GIL sub-interpreter, as sub_interpreter_guard.h does.
    PyThreadState* main_ts = PyThreadState_Get();
    PyThreadState* sub_ts = nullptr;
    const PyInterpreterConfig sub_config = {
        .use_main_obmalloc = 0,
        .allow_fork = 0,
        .allow_exec = 0,
        .allow_threads = 1,
        .allow_daemon_threads = 0,
        .check_multi_interp_extensions = 1,
        .gil = PyInterpreterConfig_OWN_GIL,
    };

    const PyStatus status = Py_NewInterpreterFromConfig(&sub_ts, &sub_config);
    if (PyStatus_Exception(status) != 0) {
        std::printf("FAIL: Py_NewInterpreterFromConfig: %s\n",
                    status.err_msg != nullptr ? status.err_msg : "(unknown error)");
        return 1;
    }

    const bool sub_ok = run("print('  sub-interpreter : ok')\n");
    Py_EndInterpreter(sub_ts);
    PyThreadState_Swap(main_ts);
    if (not sub_ok) {
        std::printf("FAIL: sub-interpreter body raised\n");
        return 1;
    }

    if (Py_FinalizeEx() < 0) {
        std::printf("FAIL: Py_FinalizeEx\n");
        return 1;
    }

    std::printf("PASS\n");
    return 0;
}
