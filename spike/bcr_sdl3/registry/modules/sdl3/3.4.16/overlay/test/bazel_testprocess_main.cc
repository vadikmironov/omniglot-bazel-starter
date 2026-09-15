// bazel_testprocess_main.cc -- runs testprocess with childprocess found in the runfiles.
//
// Not upstream. testprocess takes the path of the childprocess executable as
// its only argument and starts it with SDL_CreateProcess. ctest passes an
// absolute path. A Bazel test only has runfiles, and on Windows those are a
// manifest, not a directory tree, so a relative path does not exist there.
// This launcher resolves both executables through the runfiles library, then
// runs testprocess with the resolved childprocess path and returns its exit code.

#include <cstdio>
#include <memory>
#include <string>

#ifdef _WIN32
#include <process.h>
#else
#include <unistd.h>
#endif

#include "rules_cc/cc/runfiles/runfiles.h"

using rules_cc::cc::runfiles::Runfiles;

namespace {

std::string resolve(const Runfiles &runfiles, const char *rlocation) {
  std::string path = runfiles.Rlocation(rlocation);
#ifdef _WIN32
  // CreateProcess wants the native separator.
  for (char &c : path) {
    if (c == '/') c = '\\';
  }
#endif
  return path;
}

}  // namespace

int main(int argc, char *argv[]) {
  if (argc != 3) {
    std::fprintf(stderr, "usage: %s <testprocess rlocation> <childprocess rlocation>\n", argv[0]);
    return 2;
  }

  std::string error;
  const std::unique_ptr<Runfiles> runfiles(Runfiles::CreateForTest(&error));
  if (runfiles == nullptr) {
    std::fprintf(stderr, "bazel_testprocess_main: cannot initialise runfiles: %s\n", error.c_str());
    return 1;
  }

  const std::string testprocess = resolve(*runfiles, argv[1]);
  const std::string childprocess = resolve(*runfiles, argv[2]);
  if (testprocess.empty() || childprocess.empty()) {
    std::fprintf(stderr, "bazel_testprocess_main: not in the runfiles: %s or %s\n", argv[1], argv[2]);
    return 1;
  }

#ifdef _WIN32
  // _spawnv joins argv into one command line, so quote each argument.
  const std::string quoted_testprocess = "\"" + testprocess + "\"";
  const std::string quoted_childprocess = "\"" + childprocess + "\"";
  const char *child_argv[] = {quoted_testprocess.c_str(), quoted_childprocess.c_str(), nullptr};
  const intptr_t status = _spawnv(_P_WAIT, testprocess.c_str(), child_argv);
  if (status == -1) {
    std::perror("bazel_testprocess_main: _spawnv");
    return 1;
  }
  return static_cast<int>(status);
#else
  const char *child_argv[] = {testprocess.c_str(), childprocess.c_str(), nullptr};
  execv(testprocess.c_str(), const_cast<char *const *>(child_argv));
  std::perror("bazel_testprocess_main: execv");
  return 1;
#endif
}
