"""Dependency wiring.

The registry and service are built once in the app lifespan and handed to
routes from ``app.state``, so no request ever pays for loading devices.
"""

from __future__ import annotations

from fastapi import Request

from testforge.service import GenerationService


def get_service(request: Request) -> GenerationService:
    return request.app.state.service
