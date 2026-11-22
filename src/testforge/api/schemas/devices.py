from __future__ import annotations

from pydantic import BaseModel, Field


class AnchorStyleOut(BaseModel):
    begin: str
    end: str


class DeviceSummary(BaseModel):
    id: str
    name: str
    description: str = ""
    version: int


class DeviceDetail(DeviceSummary):
    """Everything a client needs to present a device and pre-fill its options.

    A device decides its filenames and function names inside its module, per
    case, so there is no static list of outputs to publish here.
    """

    case_heading_level: int
    step_heading_level: int = Field(
        description="Only meaningful when `step_style` is `heading`"
    )
    step_style: str = Field(
        description="`heading`: a step is a heading. `line`: a step is a plain "
        "line beginning with the word Step."
    )
    case_table: bool = Field(
        description="Whether a table under the section heading is read as a "
        "case index"
    )
    anchor: AnchorStyleOut = Field(
        description="The marker pair this device's templates carry"
    )


class DeviceListResponse(BaseModel):
    devices: list[DeviceSummary]
