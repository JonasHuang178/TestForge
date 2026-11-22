"""IR <-> DTO conversion.

The only place that knows both shapes. Keeping it here is what lets the core
models change without touching the published contract.
"""

from __future__ import annotations

from testforge.api.schemas.devices import AnchorStyleOut, DeviceDetail, DeviceSummary
from testforge.api.schemas.generations import (
    ArtifactOut,
    GenerateOptionsIn,
    GenerateRequest,
    GenerateResponse,
    GenerationSummaryOut,
)
from testforge.api.schemas.common import DiagnosticOut
from testforge.api.schemas.parse import (
    ParseOptionsIn,
    ParseResponse,
    TestCaseOut,
    TestStepOut,
)
from testforge.core.diagnostics import Diagnostic
from testforge.core.models import (
    ExistingFile,
    GeneratedArtifact,
    GenerationResult,
    ParseResult,
    TestCase,
)
from testforge.core.options import GenerateOptions, ParseOptions
from testforge.devices.python_device import PythonDevice


def diagnostic_out(diagnostic: Diagnostic) -> DiagnosticOut:
    return DiagnosticOut(
        severity=diagnostic.severity.value,
        code=diagnostic.code,
        message=diagnostic.message,
        line=diagnostic.line,
        case_index=diagnostic.case_index,
        step_index=diagnostic.step_index,
    )


def diagnostics_out(items: object) -> list[DiagnosticOut]:
    return [diagnostic_out(d) for d in items or ()]


def case_out(case: TestCase) -> TestCaseOut:
    return TestCaseOut(
        index=case.index,
        title=case.title,
        id=case.case_id,
        metadata=dict(case.metadata),
        description_md=case.description_md,
        steps=[
            TestStepOut(
                index=s.index,
                declared_index=s.declared_index,
                title=s.title,
                description_md=s.description_md,
                expected=s.expected,
                source_line=s.source_line,
            )
            for s in case.steps
        ],
        source_line=case.source_line,
    )


def parse_response(result: ParseResult) -> ParseResponse:
    return ParseResponse(
        cases=[case_out(c) for c in result.cases],
        diagnostics=diagnostics_out(result.diagnostics),
    )


def artifact_out(artifact: GeneratedArtifact) -> ArtifactOut:
    return ArtifactOut(
        path=artifact.path,
        content=artifact.content,
        mode=artifact.mode,
        anchors_filled=list(artifact.anchors_filled),
    )


def generate_response(result: GenerationResult) -> GenerateResponse:
    return GenerateResponse(
        generation_id=result.generation_id,
        device_id=result.device_id,
        artifacts=[artifact_out(a) for a in result.artifacts],
        summary=GenerationSummaryOut(
            cases=result.summary.cases,
            steps=result.summary.steps,
            functions=list(result.summary.functions),
        ),
        diagnostics=diagnostics_out(result.diagnostics),
    )


def device_summary(device: PythonDevice) -> DeviceSummary:
    return DeviceSummary(
        id=device.id,
        name=device.name,
        description=device.description,
        version=device.version,
    )


def device_detail(device: PythonDevice) -> DeviceDetail:
    return DeviceDetail(
        id=device.id,
        name=device.name,
        description=device.description,
        version=device.version,
        case_heading_level=device.parse_options.case_heading_level,
        step_heading_level=device.parse_options.step_heading_level,
        anchor=AnchorStyleOut(
            begin=device.anchor_style.begin, end=device.anchor_style.end
        ),
    )


def parse_options(options: ParseOptionsIn | None) -> ParseOptions | None:
    """Drop unset fields so the device supplies the defaults."""
    if options is None:
        return None
    provided = options.model_dump(exclude_none=True)
    return ParseOptions(**provided) if provided else None


def generate_options(options: GenerateOptionsIn | None) -> GenerateOptions | None:
    if options is None:
        return None
    provided = options.model_dump(exclude_none=True)
    return GenerateOptions(**provided) if provided else None


def existing_files(request: GenerateRequest) -> list[ExistingFile]:
    return [ExistingFile(path=f.path, content=f.content) for f in request.existing_files]
