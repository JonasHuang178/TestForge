from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from testforge.api.deps import get_service
from testforge.api.mappers import device_detail, device_summary
from testforge.api.schemas.common import ErrorEnvelope
from testforge.api.schemas.devices import DeviceDetail, DeviceListResponse
from testforge.service import GenerationService

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get(
    "",
    response_model=DeviceListResponse,
    summary="List available devices",
)
def list_devices(service: GenerationService = Depends(get_service)) -> DeviceListResponse:
    return DeviceListResponse(
        devices=[device_summary(d) for d in service.registry.list()]
    )


@router.get(
    "/{device_id}",
    response_model=DeviceDetail,
    summary="Describe one device",
    responses={404: {"model": ErrorEnvelope, "description": "No such device"}},
)
def get_device(
    device_id: str = Path(description="Device id, as returned by GET /devices"),
    service: GenerationService = Depends(get_service),
) -> DeviceDetail:
    return device_detail(service.registry.get(device_id))
