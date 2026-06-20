#include <algorithm>
#include <array>
#include <future>
#include <iostream>
#include <memory>
#include <optional>
#include <string>

#include "embedded_python_runtime.h"
#include "rules_python_current_interpreter_path_header.h"
// NOLINTBEGIN(misc-include-cleaner) — spdlog's public API surface splits across internal headers
#include "spdlog/sinks/stdout_color_sinks.h"
#include "spdlog/spdlog.h"

auto main(int /*argc*/, char** argv) -> int {
    std::shared_ptr<spdlog::logger> logger_ptr;
    try {
        logger_ptr = spdlog::stderr_color_mt("root");
    } catch (const spdlog::spdlog_ex& ex) {
        // NOLINTEND(misc-include-cleaner)
        std::cerr << "Logger initialization failed: " << ex.what() << '\n';
        return -1;
    }
    auto* logger = logger_ptr.get();

    auto runtime = EmbeddedPythonRuntime::create(argv, logger, RULES_PYTHON_RUNFILES_PATH);
    if (!runtime) {
        return -1;
    }

    runtime->add_python_library_path("_main/modules/python_lib/src");
    if (!runtime->resolve_python_library_paths()) {
        return -1;
    }

    logger->info(">> using python {}", runtime->version());

    // Release GIL before spawning async tasks.
    // CRITICAL: declared AFTER runtime so it is destroyed BEFORE the runtime,
    // restoring the GIL before Py_FinalizeEx() is called in ~EmbeddedPythonRuntime.
    auto gil_guard = runtime->release_gil();

    std::array<std::future<std::optional<std::string>>, 3> futures{{
        std::async(std::launch::async, [&runtime] -> std::optional<std::basic_string<char, std::char_traits<char>, std::allocator<char>>> {
            return runtime->call_in_subinterpreter("async-1", "python_lib.hello_world_lib",
                                                   "get_hello_world_string", {1});
        }),
        std::async(std::launch::async, [&runtime] -> std::optional<std::basic_string<char, std::char_traits<char>, std::allocator<char>>> {
            return runtime->call_in_subinterpreter("async-2", "python_lib.hello_world_lib",
                                                   "get_hello_world_string", {2});
        }),
        std::async(std::launch::async, [&runtime] -> std::optional<std::basic_string<char, std::char_traits<char>, std::allocator<char>>> {
            return runtime->call_in_subinterpreter("async-3", "python_lib.hello_world_lib",
                                                   "get_hello_world_string", {3});
        }),
    }};

    std::array<std::optional<std::string>, 3> results;
    std::ranges::transform(futures, results.begin(),
                           [](auto& future) -> auto { return future.get(); });

    logger->info(">> Results from Python subinterpreters:");
    int idx = 0;
    bool all_success = true;
    std::ranges::for_each(results, [&idx, &all_success, logger](const auto& result) -> auto {
        ++idx;
        if (result) {
            logger->info("   [async-{}] level={}: {}", idx, idx, *result);
        } else {
            logger->error("[async-{}] Failed to retrieve string", idx);
            all_success = false;
        }
    });

    return all_success ? 0 : -1;
}
