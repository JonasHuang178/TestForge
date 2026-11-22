from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from testforge.api.schemas.common import MAX_SOURCE_CHARS, DiagnosticOut


class ParseOptionsIn(BaseModel):
    """Overrides for the device's own heading conventions.

    Any field left out falls back to the device's own setting, not to the schema
    default, so omitting the object entirely is always safe.
    """

    model_config = ConfigDict(extra="forbid")

    case_heading_level: int | None = Field(default=None, ge=1, le=6)
    step_heading_level: int | None = Field(default=None, ge=1, le=6)
    require_case_prefix: bool | None = None


class ParseRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "source": "## Test Case List\n\n### print all info\n\n- ID: TC-100\n\n#### Step 1 Print the build version\n\nCall the version helper.\n\n**Expected:** A non-empty version string is printed.\n",
                "device_id": "simple_cpp",
            }
        },
    )

    source: str = Field(max_length=MAX_SOURCE_CHARS, description="The markdown test plan")
    device_id: str | None = Field(
        default=None,
        description="Optional. Supplied only to adopt that device's heading "
        "conventions so the preview matches what generation will see.",
    )
    options: ParseOptionsIn | None = None


class TestStepOut(BaseModel):
    index: int = Field(description="1-based position, which is what naming uses")
    declared_index: int | None = Field(
        default=None, description="The number written in the heading, if any"
    )
    title: str
    description_md: str = Field(description="Raw markdown, unrendered")
    expected: str | None = None
    source_line: int


class TestCaseOut(BaseModel):
    index: int
    title: str
    id: str | None = Field(default=None, description="From the plan's metadata block")
    metadata: dict[str, str] = Field(default_factory=dict)
    description_md: str = ""
    steps: list[TestStepOut] = Field(default_factory=list)
    source_line: int


class ParseResponse(BaseModel):
    cases: list[TestCaseOut]
    diagnostics: list[DiagnosticOut] = Field(default_factory=list)
