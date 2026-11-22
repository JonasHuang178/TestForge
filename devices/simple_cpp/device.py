"""Console C++ — one self-contained .cpp per plan.

The template in this folder (``main.cpp``) is an ordinary source file with no
TestForge markers in it, which is how a real project's file normally looks.
This module inserts the marker pairs itself the first time a file is created:
one above ``int main``, where the test case functions go, and one inside
``main``, where the calls go. From then on the usual rules apply — only the
regions between the markers are rewritten, and everything you add around them
is kept.

Plan layout this device expects:

    ## Test Case List

    ### print all info
    #### Step 1 Print the build version
    #### Step 2 Print the device id

Each `###` becomes one function, each `####` becomes a block inside it.
"""

import re
from pathlib import Path

from testforge.device_api import camel, identifier, output, read_text

# ------------------------------------------------------------------ identity

ID = "simple_cpp"
NAME = "Simple C++"
DESCRIPTION = "One .cpp for the whole plan: a function per test case, called from main()."

#: `## Test Case List` holds the cases, so anything above it — purpose,
#: environment, revision history — is never mistaken for one.
CASE_SECTION = "Test Case List"
CASE_HEADING_LEVEL = 3

#: Steps are plain lines under the case heading (`Step 1 Print the version`),
#: not headings of their own.
STEP_STYLE = "line"

#: The `| ID | Test Name |` table under the section heading is a case index:
#: each row's other columns become that case's metadata.
CASE_TABLE = True

#: Loaded by the web page's "load example" button, so the sample always
#: matches the device that is selected.
EXAMPLE_PLAN = "example_plan.md"

TEMPLATE = Path(__file__).parent / "main.cpp"
OUTPUT_NAME = "test_main.cpp"

CASES_ANCHOR = "TEST_CASES"
CALLS_ANCHOR = "CALLS"

#: Matches the template's `int main(...)` line, and the `return` inside it.
#: `[ \t]*` rather than `\s*`: `\s` crosses newlines, so a blank line above
#: main would be swallowed into the match and end up below the inserted block.
_MAIN_RE = re.compile(r"^[ \t]*(?:int|void)\s+main\s*\(", re.MULTILINE)
_RETURN_RE = re.compile(r"^([ \t]*)return\b[^;]*;", re.MULTILINE)

INDENT = "    "


# -------------------------------------------------------------- naming rule

def step_function_name(step):
    """Not used for the generated functions here — one function per *case*,
    not per step — but the framework asks every device for it, and a stable
    name per step is still useful in comments and reports."""
    return identifier(f"step{step.index:02d}")


def _case_function_name(case):
    """`print all info` -> `printAllInfo`."""
    return identifier(camel(case.title) or f"testCase{case.index}")


# ------------------------------------------------------- the skeleton

def _prepare_skeleton():
    """Insert the two anchor pairs into the plain template.

    Done here rather than by shipping a template with markers already in it,
    so this folder's main.cpp stays a file you can open, compile and reason
    about on its own.
    """
    text = read_text(TEMPLATE)

    main_match = _MAIN_RE.search(text)
    if main_match is None:
        raise ValueError(
            f"{TEMPLATE.name} has no `int main(` line, so there is nowhere to "
            f"put the test case functions."
        )

    cases_block = (
        f"// === TESTFORGE:{CASES_ANCHOR}:BEGIN ===\n"
        f"// === TESTFORGE:{CASES_ANCHOR}:END ===\n\n"
    )
    at = main_match.start()
    text = text[:at] + cases_block + text[at:]

    # The first `return` after main's opening brace is main's own.
    return_match = _RETURN_RE.search(text, _MAIN_RE.search(text).end())
    if return_match is None:
        raise ValueError(
            f"{TEMPLATE.name}'s main() has no `return` statement, so there is "
            f"nowhere to put the calls."
        )
    indent = return_match.group(1)
    calls_block = (
        f"{indent}// === TESTFORGE:{CALLS_ANCHOR}:BEGIN ===\n"
        f"{indent}// === TESTFORGE:{CALLS_ANCHOR}:END ===\n\n"
    )
    at = return_match.start()
    return text[:at] + calls_block + text[at:]


# -------------------------------------------------------- code fragments

def _case_function(case):
    """One test case -> one `int <name>()` with a block per step."""
    lines = [f"// Test case: {case.title}"]
    if case.case_id:
        # Comes from the ID column of the case table, so the generated code
        # can be traced back to the row that asked for it.
        lines.append(f"// Plan ID:   {case.case_id}")
    lines += [
        f"// Plan line {case.source_line}",
        f"int {_case_function_name(case)}()",
        "{",
    ]
    for step in case.steps:
        lines.append(f"{INDENT}// Step{step.index} {step.title}")
        for body_line in step.description_md.splitlines():
            lines.append(f"{INDENT}// {body_line}".rstrip())
        if step.has_expected:
            lines.append(f"{INDENT}// Expected: {step.expected}")
        lines.append(f"{INDENT}// TODO: implement this step.")
        lines.append("")
    # The function returns int, so it must return something on every path.
    lines.append(f"{INDENT}return 0;")
    lines.append("}")
    return "\n".join(lines)


def build_all(cases):
    """Every case in the plan goes into one file, so this device is called
    once with all of them.

    `build(case)` would not work here: each case would rewrite the same
    anchored region and only the last would survive.
    """
    functions = "\n\n".join(_case_function(c) for c in cases)
    calls = "\n\n".join(
        f"// Step{c.index}" + (f"  {c.case_id}" if c.case_id else "")
        + f"\n{_case_function_name(c)}();"
        for c in cases
    )
    return [
        output(
            OUTPUT_NAME,
            content=_prepare_skeleton(),
            anchors={CASES_ANCHOR: functions, CALLS_ANCHOR: calls},
        )
    ]
