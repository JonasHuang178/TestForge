"""Caller-supplied knobs for parsing and generation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ParseOptions(BaseModel):
    """How to read a test plan.

    Every device may override these, so a team can keep the plan layout it
    already uses.
    """

    model_config = ConfigDict(extra="forbid")

    case_heading_level: int = Field(default=1, ge=1, le=6)
    step_heading_level: int = Field(default=2, ge=1, le=6)
    require_case_prefix: bool = Field(
        default=False,
        description="When true, only headings starting with one of "
        "`case_prefixes` begin a test case. Useful for documents that use H1 "
        "for unrelated sections.",
    )
    case_prefixes: tuple[str, ...] = ("Test Case", "TestCase", "Testcase", "測試案例", "測試用例")
    case_section: str | None = Field(
        default=None,
        description="When set, only headings inside the section with this "
        "title count as test cases. Lets a plan carry other sections at the "
        "same heading level without them being mistaken for cases.",
    )
    section_heading_level: int | None = Field(
        default=None,
        ge=1,
        le=6,
        description="Heading level of `case_section`. Defaults to one level "
        "above `case_heading_level`.",
    )


class GenerateOptions(ParseOptions):
    """Parse options plus the generation-time overrides."""

    case_selector: int | None = Field(
        default=None,
        ge=1,
        description="Generate only this 1-based case. Omit for every case in "
        "the document.",
    )
