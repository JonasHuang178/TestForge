from __future__ import annotations

import pytest

from testforge.core.options import ParseOptions
from testforge.core.parser import MarkdownTestPlanParser


@pytest.fixture
def parser() -> MarkdownTestPlanParser:
    return MarkdownTestPlanParser()


def codes(result) -> list[str]:
    return [d.code for d in result.diagnostics]


def test_parses_cases_steps_and_metadata(parser, plan_source, plan_options) -> None:
    result = parser.parse(plan_source, plan_options)
    assert [c.title for c in result.cases] == ["print all info", "check sensors"]
    first = result.cases[0]
    assert first.metadata["id"] == "TC-100"
    assert first.case_id == "TC-100"
    assert len(first.steps) == 3
    assert first.steps[0].title == "Print the build version"


def test_description_keeps_raw_markdown(parser) -> None:
    src = (
        "# Test Case: C\n\n## Step 1: Read the id\n\n"
        "Issue the command.\n\n```\n> GET_ID\n< 0x4A\n```\n"
    )
    step = parser.parse(src).cases[0].steps[0]
    # The fenced block must survive untouched; templates decide how to show it.
    assert "```" in step.description_md
    assert "> GET_ID" in step.description_md


@pytest.mark.parametrize(
    "line,expected",
    [
        ("**Expected:** READY asserted.", "READY asserted."),
        ("**Expected**: READY asserted.", "READY asserted."),
        ("Expected: READY asserted.", "READY asserted."),
        ("Expected result: READY asserted.", "READY asserted."),
        ("預期結果：裝置回報 READY。", "裝置回報 READY。"),
        ("Expected: **READY** asserted.", "**READY** asserted."),
    ],
)
def test_expected_block_spellings(parser, line: str, expected: str) -> None:
    src = f"# Test Case: C\n\n## Step 1: S\n\nDo the thing.\n\n{line}\n"
    assert parser.parse(src).cases[0].steps[0].expected == expected


def test_heading_inside_code_fence_is_not_a_step(parser) -> None:
    src = (
        "# Test Case: C\n\n## Step 1: Real step\n\n"
        "```md\n## Step 2: Not a step\n```\n"
    )
    result = parser.parse(src)
    assert [s.title for s in result.cases[0].steps] == ["Real step"]


def test_step_numbering_variants(parser) -> None:
    src = (
        "# Test Case: C\n\n"
        "## Step 1: Alpha\n\nx\n\n"
        "## 2. Beta\n\nx\n\n"
        "## Gamma\n\nx\n"
    )
    steps = parser.parse(src).cases[0].steps
    assert [(s.index, s.declared_index, s.title) for s in steps] == [
        (1, 1, "Alpha"),
        (2, 2, "Beta"),
        (3, None, "Gamma"),
    ]


def test_misnumbered_step_warns_but_uses_position(parser) -> None:
    src = "# Test Case: C\n\n## Step 1: A\n\nx\n\n## Step 7: B\n\nx\n"
    result = parser.parse(src)
    assert "step.index_mismatch" in codes(result)
    assert result.cases[0].steps[1].index == 2


def test_no_case_heading_is_an_error(parser) -> None:
    result = parser.parse("just prose, no headings")
    assert result.cases == ()
    assert codes(result) == ["document.no_test_case"]


def test_case_without_steps_is_skipped(parser) -> None:
    src = "# Test Case: Empty\n\nSome prose only.\n"
    result = parser.parse(src)
    assert result.cases == ()
    assert codes(result) == ["case.no_steps", "document.no_usable_case"]


def test_empty_step_body_warns(parser) -> None:
    src = "# Test Case: C\n\n## Step 1: Bare\n"
    result = parser.parse(src)
    assert "step.empty_description" in codes(result)


def test_configurable_step_heading_level(parser) -> None:
    src = "# Test Case: C\n\n### Step 1: Deep\n\nx\n"
    assert parser.parse(src).cases == ()  # H3 is not a step at the default level
    result = parser.parse(src, ParseOptions(step_heading_level=3))
    assert [s.title for s in result.cases[0].steps] == ["Deep"]


def test_require_case_prefix_ignores_unrelated_h1(parser) -> None:
    src = "# Introduction\n\nprose\n\n# Test Case: Real\n\n## Step 1: A\n\nx\n"
    result = parser.parse(src, ParseOptions(require_case_prefix=True))
    assert [c.title for c in result.cases] == ["Real"]


def test_duplicate_case_title_warns(parser) -> None:
    src = (
        "# Test Case: Same\n\n## Step 1: A\n\nx\n\n"
        "# Test Case: Same\n\n## Step 1: B\n\nx\n"
    )
    assert "case.duplicate_title" in codes(parser.parse(src))


# -- steps written as lines rather than headings ----------------------------
#
# Some plans list steps compactly under each case instead of giving every one
# its own heading.

LINE_OPTS = ParseOptions(
    case_heading_level=3, case_section="Test Case List", step_style="line"
)


def test_line_steps_are_read_in_order(parser) -> None:
    src = (
        "## Test Case List\n\n### print all info\n"
        "Step 1 Print the build version  \n"
        "Step 2 Print the device id  \n"
    )
    steps = parser.parse(src, LINE_OPTS).cases[0].steps
    assert [(s.index, s.title) for s in steps] == [
        (1, "Print the build version"),
        (2, "Print the device id"),
    ]
    # The two trailing spaces are a markdown hard break, not part of the title.
    assert not steps[0].title.endswith(" ")


def test_a_line_step_needs_the_step_keyword(parser) -> None:
    # Without it, ordinary prose under a case would become steps.
    src = (
        "## Test Case List\n\n### a case\n"
        "This paragraph describes the case.\n"
        "3. A numbered note that is not a step.\n"
        "Step 1 The only real step  \n"
    )
    steps = parser.parse(src, LINE_OPTS).cases[0].steps
    assert [s.title for s in steps] == ["The only real step"]


def test_lines_under_a_line_step_become_its_description(parser) -> None:
    src = (
        "## Test Case List\n\n### a case\n"
        "Step 1 Do the thing\n"
        "Use the slow path here.\n\n"
        "**Expected:** It reports success.\n\n"
        "Step 2 Do the other thing\n"
    )
    first, second = parser.parse(src, LINE_OPTS).cases[0].steps
    assert first.description_md == "Use the slow path here."
    assert first.expected == "It reports success."
    assert second.description_md == ""


def test_misnumbered_line_step_warns_but_uses_position(parser) -> None:
    src = "## Test Case List\n\n### a case\nStep 1 A  \nStep 7 B  \n"
    result = parser.parse(src, LINE_OPTS)
    assert "step.index_mismatch" in codes(result)
    assert result.cases[0].steps[1].index == 2


def test_case_with_no_line_steps_is_skipped(parser) -> None:
    src = "## Test Case List\n\n### a case\nJust prose, no steps.\n"
    result = parser.parse(src, LINE_OPTS)
    assert result.cases == ()
    assert "case.no_steps" in codes(result)


# -- the case table ---------------------------------------------------------

TABLE_OPTS = ParseOptions(
    case_heading_level=3,
    case_section="Test Case List",
    step_style="line",
    case_table=True,
)

TABLE_PLAN = (
    "## Test Case List\n\n"
    "| ID | Test Name | Owner |\n"
    "|---|---|---|\n"
    "| TC-100 | print all info | QA |\n"
    "| TC-101 | check sensors | Firmware |\n\n"
    "### print all info\nStep 1 Print it  \n\n"
    "### check sensors\nStep 1 Read it  \n"
)


def test_table_rows_become_case_metadata(parser) -> None:
    cases = parser.parse(TABLE_PLAN, TABLE_OPTS).cases
    assert cases[0].case_id == "TC-100"
    assert cases[0].metadata["owner"] == "QA"
    assert cases[1].case_id == "TC-101"


def test_table_is_matched_by_name_case_insensitively(parser) -> None:
    src = TABLE_PLAN.replace("### print all info", "### Print All Info")
    assert parser.parse(src, TABLE_OPTS).cases[0].case_id == "TC-100"


def test_a_case_missing_from_the_table_is_noted(parser) -> None:
    src = TABLE_PLAN + "\n### extra case\nStep 1 Do it  \n"
    result = parser.parse(src, TABLE_OPTS)
    assert "case_table.missing_entry" in codes(result)
    assert result.cases[2].case_id is None


def test_a_bullet_under_the_case_beats_the_table(parser) -> None:
    # The table is the index; a line written under the case itself is more
    # specific, so it wins.
    src = TABLE_PLAN.replace(
        "### print all info\n", "### print all info\n\n- ID: TC-999\n\n"
    )
    assert parser.parse(src, TABLE_OPTS).cases[0].case_id == "TC-999"


def test_table_without_a_name_column_is_reported(parser) -> None:
    src = (
        "## Test Case List\n\n| ID | Notes |\n|---|---|\n| TC-1 | hi |\n\n"
        "### a case\nStep 1 Do it  \n"
    )
    result = parser.parse(src, TABLE_OPTS)
    assert "case_table.no_name_column" in codes(result)
    assert result.cases[0].case_id is None  # nothing invented


def test_no_table_is_not_an_error(parser) -> None:
    src = "## Test Case List\n\n### a case\nStep 1 Do it  \n"
    result = parser.parse(src, TABLE_OPTS)
    assert len(result.cases) == 1
    assert result.cases[0].case_id is None
