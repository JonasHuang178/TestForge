from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from testforge.api.schemas.common import MAX_SOURCE_CHARS, DiagnosticOut
from testforge.api.schemas.parse import ParseOptionsIn


class GenerateOptionsIn(ParseOptionsIn):
    model_config = ConfigDict(extra="forbid")

    case_selector: int | None = Field(
        default=None, ge=1, description="Generate only this 1-based case"
    )


class ExistingFileIn(BaseModel):
    """A file the client already holds, so it can be regenerated in place.

    This is how regeneration stays idempotent without the server storing
    anything: send the current content, get it back with only the anchored
    regions rewritten.
    """

    model_config = ConfigDict(extra="forbid")

    path: str = Field(
        max_length=512,
        description="Must equal the path this device produces for the case, "
        "as returned in `artifacts[].path`.",
    )
    content: str = Field(max_length=MAX_SOURCE_CHARS)


class GenerateRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "source": "## Test Case List\n\n### print all info\n\n- ID: TC-100\n\n#### Step 1 Print the build version\n\nCall the version helper.\n\n**Expected:** A non-empty version string is printed.\n",
                "device_id": "simple_cpp",
                "options": {"case_selector": 1},
                "existing_files": [],
            }
        },
    )

    source: str = Field(max_length=MAX_SOURCE_CHARS)
    device_id: str
    options: GenerateOptionsIn | None = None
    existing_files: list[ExistingFileIn] = Field(
        default_factory=list, max_length=64
    )


class ArtifactOut(BaseModel):
    path: str
    content: str
    mode: Literal["created", "updated"] = Field(
        description="`updated` when the file came in via existing_files"
    )
    anchors_filled: list[str]


class GenerationSummaryOut(BaseModel):
    cases: int
    steps: int
    functions: list[str]


class GenerateResponse(BaseModel):
    generation_id: str = Field(
        description="Correlation id for logs and bug reports only. It is NOT a "
        "resource id: nothing is stored server-side and it cannot be fetched."
    )
    device_id: str
    artifacts: list[ArtifactOut]
    summary: GenerationSummaryOut
    diagnostics: list[DiagnosticOut] = Field(default_factory=list)
