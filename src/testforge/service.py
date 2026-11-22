"""The orchestrator every surface calls.

The web page, the REST API and the CLI all go through here. None of them talk
to each other, and none of them reach into a device directly.
"""

from __future__ import annotations

import uuid

from testforge.core.assembler import inject
from testforge.core.diagnostics import DiagnosticCollector
from testforge.core.errors import UnprocessableDocumentError
from testforge.core.models import (
    ExistingFile,
    GeneratedArtifact,
    GenerationResult,
    GenerationSummary,
    ParseResult,
    TestCase,
)
from testforge.core.options import GenerateOptions, ParseOptions
from testforge.core.parser import MarkdownTestPlanParser
from testforge.devices.python_device import PythonDevice
from testforge.devices.registry import DeviceRegistry

_PARSE_KEYS = frozenset(ParseOptions.model_fields)


class GenerationService:
    def __init__(
        self,
        registry: DeviceRegistry,
        parser: MarkdownTestPlanParser | None = None,
    ) -> None:
        self._registry = registry
        self._parser = parser or MarkdownTestPlanParser()

    @property
    def registry(self) -> DeviceRegistry:
        return self._registry

    # -- parse -------------------------------------------------------------

    def parse(
        self,
        source: str,
        options: ParseOptions | None = None,
        device_id: str | None = None,
    ) -> ParseResult:
        """Read a plan without generating anything.

        ``device_id`` is optional and only used to pick up that device's
        heading conventions, so a preview matches what generation will see.
        """
        effective = options or ParseOptions()
        if device_id is not None:
            effective = self._merge_parse_options(
                self._registry.get(device_id).parse_options, options
            )
        return self._parser.parse(source, effective)

    # -- generate ----------------------------------------------------------

    def generate(
        self,
        source: str,
        device_id: str,
        options: GenerateOptions | None = None,
        existing_files: list[ExistingFile] | None = None,
    ) -> GenerationResult:
        device = self._registry.get(device_id)
        effective = self._merge_generate_options(device, options)

        diag = DiagnosticCollector()
        parsed = self._parser.parse(source, effective, diag)

        if diag.has_errors or not parsed.cases:
            raise UnprocessableDocumentError(
                "The test plan could not be turned into any test case.",
                diagnostics=diag.items,
            )

        cases = list(parsed.cases)
        if effective.case_selector is not None:
            if effective.case_selector > len(cases):
                diag.error(
                    "case_selector.out_of_range",
                    f"Requested case {effective.case_selector} but the document "
                    f"contains {len(cases)}.",
                )
                raise UnprocessableDocumentError(
                    f"Case {effective.case_selector} does not exist in this document.",
                    diagnostics=diag.items,
                )
            cases = [cases[effective.case_selector - 1]]

        existing = {f.path: f.content for f in (existing_files or [])}
        artifacts: list[GeneratedArtifact] = []
        functions: list[str] = []
        seen_paths: dict[str, int] = {}

        for case in cases:
            case_artifacts, case_functions = self._generate_case(
                device, case, existing, diag, seen_paths
            )
            artifacts.extend(case_artifacts)
            functions.extend(case_functions)

        return GenerationResult(
            generation_id=f"gen_{uuid.uuid4().hex[:24]}",
            device_id=device.id,
            artifacts=tuple(artifacts),
            summary=GenerationSummary(
                cases=len(cases),
                steps=sum(len(c.steps) for c in cases),
                functions=tuple(functions),
            ),
            diagnostics=tuple(diag.items),
        )

    # -- internals ---------------------------------------------------------

    def _generate_case(
        self,
        device: PythonDevice,
        case: TestCase,
        existing: dict[str, str],
        diag: DiagnosticCollector,
        seen_paths: dict[str, int],
    ) -> tuple[list[GeneratedArtifact], list[str]]:
        """Build one case.

        The device decides the filenames, the function names and the code. The
        framework owns anchor injection, so idempotent regeneration and
        line-ending preservation hold whatever the device's module does.
        """
        info = device.case_info(case)
        outputs = device.build(info)

        artifacts: list[GeneratedArtifact] = []
        for spec in outputs:
            path = spec.path
            if path in seen_paths:
                diag.warning(
                    "output.path_collision",
                    f"Case {case.index} writes {path!r}, which case "
                    f"{seen_paths[path]} already produced; the later one wins.",
                    line=case.source_line,
                    case_index=case.index,
                )
            seen_paths[path] = case.index

            base = existing.get(path)
            mode = "updated" if base is not None else "created"
            if base is None:
                base = spec.skeleton

            content, filled = inject(base, spec.anchors, device.anchor_style)
            artifacts.append(
                GeneratedArtifact(
                    path=path, content=content, mode=mode, anchors_filled=filled
                )
            )

        return artifacts, [s.function_name for s in info.steps]

    @staticmethod
    def _merge_parse_options(
        parse_defaults: ParseOptions, options: ParseOptions | None
    ) -> ParseOptions:
        merged = parse_defaults.model_dump()
        if options is not None:
            provided = options.model_dump(exclude_unset=True)
            merged.update({k: v for k, v in provided.items() if k in _PARSE_KEYS})
        return ParseOptions(**merged)

    @classmethod
    def _merge_generate_options(
        cls, device: PythonDevice, options: GenerateOptions | None
    ) -> GenerateOptions:
        """The device supplies the defaults; the request overrides them.

        Only fields the caller actually sent count as overrides, so omitting
        one falls back to the device rather than to the schema default.
        """
        base = cls._merge_parse_options(device.parse_options, options).model_dump()
        provided = {} if options is None else options.model_dump(exclude_unset=True)
        return GenerateOptions(**base, case_selector=provided.get("case_selector"))
