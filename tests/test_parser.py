from __future__ import annotations

import pytest

from testforge.core.options import ParseOptions
from testforge.core.parser import MarkdownTestPlanParser


@pytest.fixture
def parser() -> MarkdownTestPlanParser:
    return MarkdownTestPlanParser()


def codes(result) -> list[str]:
    return [d.code for d in result.diagnostics]


def test_parses_cases_steps_and_metadata(parser, plan_source: str) -> None:
    result = parser.parse(plan_source)
    assert [c.title for c in result.cases] == [
        "Sensor Initialization Sequence",
        "Sensor Fault Recovery",
    ]
    first = result.cases[0]
    assert first.metadata["id"] == "TC-001"
    assert first.case_id == "TC-001"
    assert len(first.steps) == 4
    assert first.steps[0].title == "Power on the device"


def test_description_keeps_raw_markdown(parser, plan_source: str) -> None:
    step = parser.parse(plan_source).cases[0].steps[1]
    # The fenced block must survive untouched; templates decide how to show it.
    assert "```" in step.description_md
    assert "> 0x01 0x00" in step.description_md


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
