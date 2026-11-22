from __future__ import annotations

from fastapi import APIRouter, Depends

from testforge.api.deps import get_service
from testforge.api.mappers import parse_options, parse_response
from testforge.api.schemas.common import ErrorEnvelope
from testforge.api.schemas.parse import ParseRequest, ParseResponse
from testforge.core.diagnostics import Severity
from testforge.core.errors import UnprocessableDocumentError
from testforge.service import GenerationService

router = APIRouter(tags=["parse"])


@router.post(
    "/parse",
    response_model=ParseResponse,
    summary="Parse a plan without generating code",
    description=(
        "A dry run: returns the detected cases and steps plus every diagnostic, "
        "without needing a device or producing any code. Intended for live "
        "preview and for validating a plan's format.\n\n"
        "Recoverable problems come back as `diagnostics` with HTTP 200. A plan "
        "that yields no usable case is a 422 whose body carries the same "
        "`diagnostics` array, so one rendering path handles both."
    ),
    responses={
        422: {"model": ErrorEnvelope, "description": "No usable test case in the plan"},
        400: {"model": ErrorEnvelope, "description": "Malformed request body"},
    },
)
def parse(
    request: ParseRequest,
    service: GenerationService = Depends(get_service),
) -> ParseResponse:
    result = service.parse(
        request.source,
        parse_options(request.options),
        device_id=request.device_id,
    )
    if not result.cases or any(d.severity is Severity.ERROR for d in result.diagnostics):
        raise UnprocessableDocumentError(
            "The test plan could not be turned into any test case.",
            diagnostics=list(result.diagnostics),
        )
    return parse_response(result)
