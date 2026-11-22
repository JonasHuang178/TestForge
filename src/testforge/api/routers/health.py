from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from testforge import __version__
from testforge.api.deps import get_service
from testforge.service import GenerationService

router = APIRouter(tags=["meta"])


class HealthResponse(BaseModel):
    status: str
    version: str
    devices: int


@router.get("/health", response_model=HealthResponse, summary="Liveness and device count")
def health(service: GenerationService = Depends(get_service)) -> HealthResponse:
    return HealthResponse(status="ok", version=__version__, devices=len(service.registry))
