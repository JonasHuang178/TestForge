"""Simple C++ — the smallest device worth copying.

One test case produces one self-contained .cpp with a main(), so the output
compiles and runs on its own with nothing else to link. Start here; see
``devices/demo_board/`` for a device that emits a header and a source file.
"""

from testforge.device_api import cstr, identifier, output, pascal, snake

ID = "simple_cpp"
NAME = "Simple C++"
DESCRIPTION = "One self-contained .cpp per test case, with its own main()."

# `## Step 1: ...` is a level-2 heading.
STEP_HEADING_LEVEL = 2


def step_function_name(step):
    """One step -> one function name. This is the rule you would change."""
    return identifier(f"Step{step.index:02d}_{pascal(step.title)}")


def build(case):
    steps = []
    for step in case.steps:
        lines = [
            f"// Step {step.index}: {step.title}  (plan line {step.source_line})",
            f"void {step.function_name}() {{",
            f'  std::printf("[{step.index:02d}] {cstr(step.title)}\\n");',
            "",
            "  // TODO: implement this step.",
        ]
        if step.has_expected:
            # Starting at `false` keeps an unwritten test red. A test that
            # passes before anyone has implemented it is worse than no test.
            lines += [f'  Check(false, "{cstr(step.expected)}");']
        lines.append("}")
        steps.append("\n".join(lines))

    calls = "\n".join(f"{s.function_name}();" for s in case.steps)

    return [
        output(
            f"test_{snake(case.title)}.cpp",
            template="test_case.cpp",
            anchors={"STEPS": "\n\n".join(steps), "CALLS": calls},
            CASE_TITLE=case.title,
        )
    ]
