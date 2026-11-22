"""Demo board — a worked example of a TestForge device.

Copy this folder to add a device of your own. Everything that differs between
devices lives in this file: how a step becomes a function name, which files
come out, and what goes into each one. Edit it freely — it is ordinary Python.

What the framework still guarantees, whatever you write here:

* only the regions between the anchor markers are rewritten, so hand-written
  code elsewhere in a generated file survives regeneration;
* a file keeps the line endings it already had;
* the same plan always produces byte-identical output.

Required: ID, NAME, step_function_name(step), build(case).
Optional: DESCRIPTION, VERSION, STEP_HEADING_LEVEL, CASE_HEADING_LEVEL.
"""

from testforge.device_api import comment, cstr, guard, identifier, output, pascal, snake

# --------------------------------------------------------------- identity

ID = "demo_board"          # must match this folder's name
NAME = "Demo Board"
DESCRIPTION = "Worked example: one header, one source, three anchors."
VERSION = 1

#: Which heading level starts a step in this device's test plans.
#: `## Step 1: ...` is level 2.
STEP_HEADING_LEVEL = 2


# ----------------------------------------------------------- naming rule

def step_function_name(step):
    """Turn one step into a C++ function name.

    The index comes first so the name survives a retitle, keeps the plan's
    order in the generated file, and stays unique without a dedup suffix.
    Change this line and every generated name changes with it.
    """
    return identifier(f"TestStep_{step.index:02d}_{pascal(step.title)}")


# ------------------------------------------------------- code fragments
#
# Plain Python building plain strings. Indentation inside an anchor is handled
# for you: the framework re-indents a fragment to match its BEGIN marker, so
# these functions never need to know where in the file they land.


def _declarations(case):
    lines = []
    for step in case.steps:
        lines.append(f"/// Step {step.index}: {step.title}")
        lines.append(f"void {step.function_name}(TestContext& ctx);")
    return "\n".join(lines)


def _calls(case):
    return "\n".join(
        f'DEMO_RUN_STEP(ctx, {s.index}, "{cstr(s.title)}", {s.function_name});'
        for s in case.steps
    )


def _definitions(case):
    blocks = []
    for step in case.steps:
        header = [
            "// " + "-" * 72,
            f"// Step {step.index}: {step.title}",
            f"// Plan line {step.source_line}",
        ]
        if step.description_md:
            header += ["//", comment(step.description_md, "//   ")]
        if step.has_expected:
            header += ["//", f"//   Expected: {step.expected}"]
        header.append("// " + "-" * 72)

        body = [
            f"void {step.function_name}(TestContext& ctx) {{",
            f'  ctx.Log("{cstr(step.title)}");',
            "",
            "  // TODO: drive the board to perform this step.",
        ]
        if step.has_expected:
            body += [
                "",
                "  // An unimplemented step fails on purpose: a test that passes",
                "  // before anyone has written it is worse than one that is red.",
                f'  DEMO_EXPECT(ctx, false, "{cstr(step.expected)}");',
            ]
        body.append("}")

        blocks.append("\n".join(header + body))
    return "\n\n".join(blocks)


# ------------------------------------------------------------ the outputs

def build(case):
    """Return the files to produce for one test case.

    `output(path, template, anchors, **variables)`:
      path       the generated filename
      template   a file in this folder, used only when `path` does not exist yet
      anchors    anchor name -> the code to place between its markers
      variables  @@NAME@@ placeholders in the template, substituted on creation

    Variables are applied only when the file is first created. Regenerating an
    existing file rewrites the anchored regions and leaves everything else
    exactly as it was.
    """
    base = f"test_{snake(case.title)}"
    header = f"{base}.h"
    source = f"{base}.cpp"
    runner = f"Run{pascal(case.title)}"

    common = {
        "CASE_TITLE": case.title,
        "CASE_ID": case.case_id or "(none)",
        "RUNNER": runner,
    }

    return [
        output(
            header,
            template="test_case.h",
            anchors={"STEP_DECLS": _declarations(case)},
            GUARD=guard(header),
            **common,
        ),
        output(
            source,
            template="test_case.cpp",
            anchors={
                "STEP_CALLS": _calls(case),
                "STEP_DEFS": _definitions(case),
            },
            HEADER=header,
            STEP_COUNT=str(len(case.steps)),
            **common,
        ),
    ]
