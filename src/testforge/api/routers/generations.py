from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status

from testforge.api.deps import get_service
from testforge.api.mappers import existing_files, generate_options, generate_response
from testforge.api.schemas.common import ErrorEnvelope
from testforge.api.schemas.generations import GenerateRequest, GenerateResponse
from testforge.core.errors import OutputFormatError
from testforge.core.models import GenerationResult
from testforge.packaging import artifacts_to_zip, safe_filename, zip_filename
from testforge.service import GenerationService

router = APIRouter(tags=["generations"])


class MultipleArtifactsError(OutputFormatError):
    code = "format.multiple_artifacts"


@router.post(
    "/generations",
    response_model=GenerateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate test code from a plan",
    description=(
        "Nothing is stored server-side. `generation_id` is a correlation id for "
        "logs, not a resource that can be fetched.\n\n"
        "To regenerate an existing file in place, send its current content in "
        "`existing_files`; only the regions between the device's anchor markers "
        "are rewritten and the result comes back with `mode: \"updated\"`.\n\n"
        "`?format=zip` returns the same generation as a zip archive and "
        "`?format=file` as the single file's raw text, so an ordinary HTML form "
        "post can trigger a browser download without any JavaScript."
    ),
    responses={
        400: {"model": ErrorEnvelope, "description": "Malformed body or bad naming pattern"},
        404: {"model": ErrorEnvelope, "description": "No such device"},
        413: {"model": ErrorEnvelope, "description": "Source exceeds the size limit"},
        422: {
            "model": ErrorEnvelope,
            "description": "Unusable plan, or missing anchors in existing_files",
        },
    },
)
def create_generation(
    request: GenerateRequest,
    format: Literal["json", "zip", "file"] = Query(
        default="json",
        description="Representation to return. `json` is the API default; the "
        "other two are browser downloads.",
    ),
    service: GenerationService = Depends(get_service),
) -> Response | GenerateResponse:
    result = service.generate(
        request.source,
        request.device_id,
        generate_options(request.options),
        existing_files(request),
    )
    if format == "zip":
        return _zip_response(result)
    if format == "file":
        return _single_file_response(result)
    return generate_response(result)


def _zip_response(result: GenerationResult) -> Response:
    return Response(
        content=artifacts_to_zip(result),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename(result)}"'
        },
    )


def _single_file_response(result: GenerationResult) -> Response:
    if len(result.artifacts) != 1:
        raise MultipleArtifactsError(
            f"This generation produced {len(result.artifacts)} files; "
            f"`format=file` needs exactly one. Use format=zip, or narrow the "
            f"request with options.case_selector.",
            details={"paths": [a.path for a in result.artifacts]},
        )
    artifact = result.artifacts[0]
    return Response(
        content=artifact.content,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename(artifact.path)}"'
        },
    )
