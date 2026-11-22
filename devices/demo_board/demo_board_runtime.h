// Minimal runtime so the generated code compiles and runs as-is.
//
// This file is NOT part of generation — device.py never references it, and
// TestForge does not copy it anywhere. Replace it with your real test
// framework's header; the only thing the templates assume is the handful of
// symbols below.

#ifndef DEMO_BOARD_RUNTIME_H
#define DEMO_BOARD_RUNTIME_H

#include <cstdio>
#include <string>
#include <vector>

namespace demo_board {

struct Failure {
  int step;
  std::string expectation;
};

class TestContext {
 public:
  void BeginStep(int index, const std::string& title) {
    step_ = index;
    std::printf("[%02d] %s\n", index, title.c_str());
  }

  void Log(const std::string& message) {
    std::printf("     %s\n", message.c_str());
  }

  void Expect(bool ok, const std::string& expectation) {
    if (ok) return;
    failures_.push_back(Failure{step_, expectation});
    std::printf("     FAIL: %s\n", expectation.c_str());
  }

  bool passed() const { return failures_.empty(); }
  const std::vector<Failure>& failures() const { return failures_; }

 private:
  int step_ = 0;
  std::vector<Failure> failures_;
};

}  // namespace demo_board

#define DEMO_RUN_STEP(ctx, index, title, fn) \
  do {                                       \
    (ctx).BeginStep((index), (title));       \
    fn(ctx);                                 \
  } while (0)

#define DEMO_EXPECT(ctx, cond, text) (ctx).Expect((cond), (text))

#endif  // DEMO_BOARD_RUNTIME_H
