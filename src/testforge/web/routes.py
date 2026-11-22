"""HTML routes for the operator-facing page.

Every handler calls ``GenerationService`` directly and renders a Jinja2
template. Nothing here goes through the REST API, so the two surfaces can
evolve independently and a failure in one does not implicate the other.

Handlers are sync ``def``: parsing and generation are CPU-bound, so FastAPI's
threadpool is the right place for them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from testforge.api.deps import get_service
from testforge.core.diagnostics import Severity
from testforge.core.errors import TestForgeError, UnprocessableDocumentError
from testforge.core.options import GenerateOptions, ParseOptions
from testforge.packaging import artifacts_to_zip, safe_filename, zip_filename
from testforge.service import GenerationService

WEB_DIR = Path(__file__).parent
TEMPLATE_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

router = APIRouter(include_in_schema=False)

#: Order used when sorting diagnostics for display: worst first.
_SEVERITY_RANK = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}


def _diagnostic_rows(diagnostics) -> list[dict]:
    return [
        {
            "severity": d.severity.value,
            "code": d.code,
            "message": d.message,
            "line": d.line,
            "case_index": d.case_index,
            "step_index": d.step_index,
        }
        for d in sorted(diagnostics, key=lambda d: (_SEVERITY_RANK[d.severity], d.line or 0))
    ]


def _parse_options(step_level: int | None) -> ParseOptions | None:
    return ParseOptions(step_heading_level=step_level) if step_level else None


@router.get("/", response_class=HTMLResponse)
def index(request: Request, service: GenerationService = Depends(get_service)):
    """The editor page. Everything else on this router returns a fragment."""
    devices = [
        {
            "id": d.manifest.id,
            "name": d.manifest.name,
            "description": d.manifest.description,
            "step_heading_level": d.manifest.parse.step_heading_level,
            "naming": d.manifest.naming.step_function,
            "outputs": [o.path for o in d.manifest.outputs],
        }
        for d in service.registry.list()
    ]
    example = _example_plan()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"devices": devices, "example": example},
    )


@router.post("/preview", response_class=HTMLResponse)
def preview(
    request: Request,
    source: str = Form(default=""),
    device_id: str = Form(default=""),
    step_level: int | None = Form(default=None),
    service: GenerationService = Depends(get_service),
):
    """Parse without generating, for the live outline beside the editor."""
    if not source.strip():
        return templates.TemplateResponse(
            request=request, name="_preview.html", context={"empty": True}
        )
    try:
        result = service.parse(
            source,
            _parse_options(step_level),
            device_id=device_id or None,
        )
    except TestForgeError as exc:
        return _fragment_error(request, exc)

    return templates.TemplateResponse(
        request=request,
        name="_preview.html",
        context={
            "cases": result.cases,
            "diagnostics": _diagnostic_rows(result.diagnostics),
            "step_total": sum(len(c.steps) for c in result.cases),
            "blocked": any(d.severity is Severity.ERROR for d in result.diagnostics),
        },
    )


@router.post("/generate", response_class=HTMLResponse)
def generate(
    request: Request,
    source: str = Form(default=""),
    device_id: str = Form(...),
    case_selector: int | None = Form(default=None),
    step_level: int | None = Form(default=None),
    naming_pattern: str = Form(default=""),
    service: GenerationService = Depends(get_service),
):
    """Generate and render the artifacts as tabs."""
    try:
        result = service.generate(
            source,
            device_id,
            GenerateOptions(
                case_selector=case_selector,
                naming_pattern=naming_pattern or None,
                **({"step_heading_level": step_level} if step_level else {}),
            ),
        )
    except UnprocessableDocumentError as exc:
        return _fragment_error(request, exc, diagnostics=exc.diagnostics)
    except TestForgeError as exc:
        return _fragment_error(request, exc)

    return templates.TemplateResponse(
        request=request,
        name="_artifacts.html",
        context={
            "artifacts": result.artifacts,
            "summary": result.summary,
            "diagnostics": _diagnostic_rows(result.diagnostics),
            "device_id": result.device_id,
        },
    )


@router.post("/download")
def download(
    source: str = Form(default=""),
    device_id: str = Form(...),
    case_selector: int | None = Form(default=None),
    step_level: int | None = Form(default=None),
    naming_pattern: str = Form(default=""),
    what: Literal["zip", "file"] = Form(default="zip"),
    path: str = Form(default=""),
    service: GenerationService = Depends(get_service),
) -> Response:
    """Re-run the generation and return it as a download.

    Regenerating rather than caching the previous result is deliberate: output
    is deterministic, so the download is identical to what was displayed, and
    the server stays stateless.
    """
    result = service.generate(
        source,
        device_id,
        GenerateOptions(
            case_selector=case_selector,
            naming_pattern=naming_pattern or None,
            **({"step_heading_level": step_level} if step_level else {}),
        ),
    )

    if what == "file" and path:
        for artifact in result.artifacts:
            if artifact.path == path:
                return Response(
                    content=artifact.content,
                    media_type="text/plain; charset=utf-8",
                    headers={
                        "Content-Disposition": f'attachment; filename="{safe_filename(path)}"'
                    },
                )

    return Response(
        content=artifacts_to_zip(result),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename(result)}"'},
    )


def _fragment_error(request: Request, exc: TestForgeError, diagnostics=()) -> HTMLResponse:
    """Render a domain error inside the results pane.

    The page shows the failure where the result would have gone rather than
    navigating away, so the author keeps their plan and their place.
    """
    return templates.TemplateResponse(
        request=request,
        name="_error.html",
        context={
            "code": exc.code,
            "message": exc.message,
            "diagnostics": _diagnostic_rows(diagnostics),
        },
        status_code=200,
    )


def _example_plan() -> str:
    """The bundled sample, so the page is usable without hunting for a file."""
    candidate = WEB_DIR.parents[2] / "examples" / "sensor_init.md"
    if candidate.is_file():
        return candidate.read_text(encoding="utf-8")
    return (
        "# Test Case: Sensor Initialization Sequence\n\n"
        "- ID: TC-001\n\n"
        "## Step 1: Power on the device\n\n"
        "Drive the enable line high and wait for the regulator to settle.\n\n"
        "**Expected:** The READY flag is asserted within 500 ms.\n"
    )
