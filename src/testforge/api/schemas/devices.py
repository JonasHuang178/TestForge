from __future__ import annotations

from pydantic import BaseModel, Field


class AnchorStyleOut(BaseModel):
    begin: str
    end: str


class OutputSpecOut(BaseModel):
    path: str = Field(description="Filename pattern, e.g. test_{case_snake}.cpp")
    anchors: list[str] = Field(description="Anchors this file carries")


class DeviceSummary(BaseModel):
    id: str
    name: str
    description: str = ""
    version: int
    kind: str = Field(
        description="`manifest` for a declarative device, `python` for one "
        "whose rules are written in a device.py module"
    )


class DeviceDetail(DeviceSummary):
    """Everything a client needs to show a device and pre-fill its options."""

    step_function_pattern: str | None = Field(
        default=None,
        description="Null for a Python device: it names steps inside build(), "
        "so there is no static pattern.",
    )
    case_heading_level: int
    step_heading_level: int
    anchor: AnchorStyleOut
    outputs: list[OutputSpecOut] = Field(
        default_factory=list,
        description="Empty for a Python device: its filenames are computed per "
        "case inside build().",
    )


class DeviceListResponse(BaseModel):
    devices: list[DeviceSummary]
