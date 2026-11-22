// Minimal reference runtime for the example device.
//
// This file is NOT part of code generation; the loader ignores support/.
// It exists so the generated output can be compiled and run as-is, and so a
// device author can see exactly which symbols the templates assume.

#ifndef TESTFORGE_RUNTIME_H
#define TESTFORGE_RUNTIME_H

#include <cstdio>
#include <string>
#include <vector>

namespace testforge {

struct StepFailure {
  int step_index;
  std::string step_title;
  std::string expectation;
};

/// Carried through every step function; collects the outcome of the case.
class TestContext {
 public:
  void Log(const std::string& message) {
    std::printf("[step %d] %s\n", current_step_, message.c_str());
  }

  void BeginStep(int index, const std::string& title) {
    current_step_ = index;
    current_title_ = title;
    std::printf("[step %d] >>> %s\n", index, title.c_str());
  }

  void Expect(bool condition, const std::string& expectation) {
    if (condition) {
      return;
    }
    failures_.push_back(StepFailure{current_step_, current_title_, expectation});
    std::printf("[step %d] FAIL: %s\n", current_step_, expectation.c_str());
  }

  bool passed() const { return failures_.empty(); }
  const std::vector<StepFailure>& failures() const { return failures_; }

 private:
  int current_step_ = 0;
  std::string current_title_;
  std::vector<StepFailure> failures_;
};

}  // namespace testforge

using testforge::TestContext;

#define TESTFORGE_RUN_STEP(ctx, index, title, fn) \
  do {                                            \
    (ctx).BeginStep((index), (title));            \
    fn(ctx);                                      \
  } while (0)

#define TESTFORGE_EXPECT(ctx, cond, expectation) (ctx).Expect((cond), (expectation))

#endif  // TESTFORGE_RUNTIME_H
