#include <SDL3/SDL_log.h>
#include <SDL3/SDL_version.h>

auto main(int /*argc*/, char** /*argv*/) -> int {
    const int compiled = SDL_VERSION;
    const int linked = SDL_GetVersion();

    SDL_Log("Spike compiled against SDL version %d.%d.%d ...\n",
            SDL_VERSIONNUM_MAJOR(compiled), SDL_VERSIONNUM_MINOR(compiled),
            SDL_VERSIONNUM_MICRO(compiled));
    SDL_Log("Spike is linking against SDL version %d.%d.%d.\n",
            SDL_VERSIONNUM_MAJOR(linked), SDL_VERSIONNUM_MINOR(linked),
            SDL_VERSIONNUM_MICRO(linked));

    return 0;
}