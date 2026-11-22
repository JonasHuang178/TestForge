from __future__ import annotations

import io
import re
import zipfile
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status

from testforge.api.deps import get_service
from testforge.api.mappers import existing_files, generate_options, generate_response
from testforge.api.schemas.common import ErrorEnvelope
from testforge.api.schemas.generations import GenerateRequest, GenerateResponse
from testforge.core.errors import OutputFormatError
from testforge.core.models import GenerationResult
from testforge.service import GenerationService

router = APIRouter(tags=["generations"])

#: A fixed timestamp keeps the zip byte-identical across runs, which matters
#: because the same determinism is what golden-file tests rely on.
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)

_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


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


def _safe_filename(name: str) -> str:
    cleaned = _UNSAFE_FILENAME.sub("_", name).strip("_")
    return cleaned or "generated"


def _zip_response(result: GenerationResult) -> Response:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for artifact in result.artifacts:
            info = zipfile.ZipInfo(artifact.path, date_time=_ZIP_EPOCH)
            info.external_attr = 0o644 << 16
            archive.writestr(info, artifact.content)
    filename = _safe_filename(f"{result.device_id}_generated") + ".zip"
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
            "Content-Disposition": f'attachment; filename="{_safe_filename(artifact.path)}"'
        },
    )
