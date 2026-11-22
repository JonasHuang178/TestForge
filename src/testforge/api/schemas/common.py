from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

#: Upper bound on a submitted plan. Generous for a hand-written document, low
#: enough that a stray upload cannot exhaust memory.
MAX_SOURCE_CHARS = 1_000_000


class DiagnosticOut(BaseModel):
    """A non-fatal problem found in the submitted plan.

    Clients should branch on `code`, never on `message`.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "severity": "warning",
                "code": "step.empty_description",
                "message": "Step 3 ('Verify idle current draw') has no description body.",
                "line": 35,
                "case_index": 1,
                "step_index": 3,
            }
        }
    )

    severity: str = Field(description="error | warning | info")
    code: str = Field(description="Stable identifier for this kind of problem")
    message: str = Field(description="Human-readable explanation; may be reworded")
    line: int | None = Field(default=None, description="1-based line in the submitted source")
    case_index: int | None = None
    step_index: int | None = None


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    """The body of every 4xx and 5xx response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": {
                    "code": "device_not_found",
                    "message": "Unknown device 'foo'. Known devices: example_device",
                    "details": {"device_id": "foo", "known": ["example_device"]},
                },
                "diagnostics": [],
            }
        }
    )

    error: ErrorBody
    diagnostics: list[DiagnosticOut] = Field(
        default_factory=list,
        description="Populated when the failure came from the content of the "
        "plan, so the same rendering code handles success and failure.",
    )
