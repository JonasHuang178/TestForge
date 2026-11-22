"""Domain exception -> HTTP response.

Core raises only ``TestForgeError`` subclasses and never imports FastAPI; the
whole mapping lives here, which is what keeps core usable from the CLI and
from plain unit tests.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from testforge.api.mappers import diagnostics_out
from testforge.api.schemas.common import MAX_SOURCE_CHARS, ErrorBody, ErrorEnvelope
from testforge.core.errors import (
    AnchorError,
    DeviceNotFoundError,
    DeviceDefinitionError,
    NamingPatternError,
    OutputFormatError,
    TemplateRenderError,
    TestForgeError,
    UnprocessableDocumentError,
)

logger = logging.getLogger("testforge.api")

#: Everything not listed here falls through to 500.
_STATUS_BY_TYPE: tuple[tuple[type[TestForgeError], int], ...] = (
    (DeviceNotFoundError, status.HTTP_404_NOT_FOUND),
    # The submitted plan, or the file it was to be merged into, cannot be used.
    (UnprocessableDocumentError, 422),
    (AnchorError, 422),
    # A bad naming pattern or an impossible `format` is a malformed request,
    # not a content problem.
    (NamingPatternError, status.HTTP_400_BAD_REQUEST),
    (OutputFormatError, status.HTTP_400_BAD_REQUEST),
    # Both of these mean the device itself is broken: our fault, not the caller's.
    (DeviceDefinitionError, status.HTTP_500_INTERNAL_SERVER_ERROR),
    (TemplateRenderError, status.HTTP_500_INTERNAL_SERVER_ERROR),
)


def status_for(exc: TestForgeError) -> int:
    for exc_type, code in _STATUS_BY_TYPE:
        if isinstance(exc, exc_type):
            return code
    return status.HTTP_500_INTERNAL_SERVER_ERROR


def _envelope(exc: TestForgeError, http_status: int) -> JSONResponse:
    # A 5xx means the fault is ours; details may name internal paths, so they
    # are logged rather than returned.
    server_error = http_status >= 500
    body = ErrorEnvelope(
        error=ErrorBody(
            code=exc.code,
            message=exc.message,
            details={} if server_error else exc.details,
        ),
        diagnostics=diagnostics_out(getattr(exc, "diagnostics", ())),
    )
    return JSONResponse(status_code=http_status, content=body.model_dump())


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(TestForgeError)
    def _handle_domain_error(_: Request, exc: TestForgeError) -> JSONResponse:
        http_status = status_for(exc)
        if http_status >= 500:
            logger.exception("Unhandled domain error: %s", exc.message, exc_info=exc)
        return _envelope(exc, http_status)

    @app.exception_handler(RequestValidationError)
    def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # FastAPI's default is 422, which this API reserves for "your plan
        # cannot be used". A body that does not match the schema is a 400.
        errors = exc.errors()
        oversize = any(
            e.get("type") == "string_too_long"
            and "source" in [str(p) for p in e.get("loc", ())]
            for e in errors
        )
        if oversize:
            return JSONResponse(
                status_code=413,
                content=ErrorEnvelope(
                    error=ErrorBody(
                        code="source_too_large",
                        message=f"`source` exceeds the {MAX_SOURCE_CHARS} character limit.",
                        details={"limit_chars": MAX_SOURCE_CHARS},
                    )
                ).model_dump(),
            )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorEnvelope(
                error=ErrorBody(
                    code="request_invalid",
                    message="The request body does not match the expected schema.",
                    details={"errors": _safe_errors(errors)},
                )
            ).model_dump(),
        )


def _safe_errors(errors: list[dict]) -> list[dict]:
    """Strip the offending input back out of validation errors.

    A rejected field can hold an entire test plan; echoing it would make the
    error response larger than the request.
    """
    return [
        {"loc": [str(p) for p in e.get("loc", ())], "msg": e.get("msg", ""), "type": e.get("type", "")}
        for e in errors
    ]
