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


class DeviceDetail(DeviceSummary):
    """Everything a client needs to show a device and pre-fill its options."""

    step_function_pattern: str
    case_heading_level: int
    step_heading_level: int
    anchor: AnchorStyleOut
    outputs: list[OutputSpecOut]


class DeviceListResponse(BaseModel):
    devices: list[DeviceSummary]
