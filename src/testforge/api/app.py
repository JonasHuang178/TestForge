"""Application factory.

Devices are loaded once in the lifespan and a broken device raises there, so
a process that starts is a process whose devices are all valid.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Iterable

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.staticfiles import StaticFiles

from testforge import __version__
from testforge.api.errors import register_error_handlers
from testforge.api.routers import devices, generations, health, parse
from testforge.api.schemas.common import MAX_SOURCE_CHARS, ErrorBody, ErrorEnvelope
from testforge.devices.registry import DeviceRegistry
from testforge.service import GenerationService
from testforge.web import routes as web_routes

logger = logging.getLogger("testforge.api")

API_PREFIX = "/api/v1"

#: Rejected before the body is read. Larger than MAX_SOURCE_CHARS because a
#: request may legitimately carry a plan plus the files to regenerate.
MAX_REQUEST_BYTES = 8 * 1024 * 1024

DESCRIPTION = """
Generate C++ test code from markdown test plans.

**Stateless.** Nothing is stored between requests. A generation returns its
artifacts inline; to regenerate a file in place, send the file back in
`existing_files` and only the anchored regions are rewritten.

**Diagnostics, not errors.** Hand-written plans are messy, so recoverable
problems come back in a `diagnostics` array alongside a 200 rather than as a
4xx. Branch on `diagnostics[].code`, never on the message text.
"""


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject an oversized request before its body is buffered."""

    def __init__(self, app, max_bytes: int = MAX_REQUEST_BYTES) -> None:
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        raw = request.headers.get("content-length")
        if raw and raw.isdigit() and int(raw) > self._max_bytes:
            return JSONResponse(
                status_code=413,
                content=ErrorEnvelope(
                    error=ErrorBody(
                        code="request_too_large",
                        message=f"Request body exceeds {self._max_bytes} bytes.",
                        details={"limit_bytes": self._max_bytes},
                    )
                ).model_dump(),
            )
        return await call_next(request)


def create_app(device_roots: Iterable[Path] | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        registry = DeviceRegistry.from_roots(device_roots)
        app.state.service = GenerationService(registry)
        logger.info(
            "Loaded %d device(s): %s",
            len(registry),
            ", ".join(d.id for d in registry.list()) or "(none)",
        )
        yield

    app = FastAPI(
        title="TestForge",
        version=__version__,
        description=DESCRIPTION,
        lifespan=lifespan,
    )
    app.add_middleware(BodySizeLimitMiddleware)
    register_error_handlers(app)

    for router in (health.router, devices.router, parse.router, generations.router):
        app.include_router(router, prefix=API_PREFIX)

    # The web layer is a sibling of the API, not a client of it: its handlers
    # call GenerationService directly. It is mounted last so that its catch-all
    # root route cannot shadow an API path.
    app.mount(
        "/static",
        StaticFiles(directory=str(web_routes.STATIC_DIR)),
        name="static",
    )
    app.include_router(web_routes.router)

    return app


#: Module-level app for `uvicorn testforge.api.app:app`.
app = create_app()
